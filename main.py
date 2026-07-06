import asyncio
import json
import logging
import os
import warnings

import boto3
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel

# create_react_agent is deprecated in favor of langchain.agents.create_agent,
# but as of langchain==1.3.11/langgraph==1.2.7 the new create_agent does not
# propagate on_chat_model_stream events through astream_events (verified: a
# real streaming run produced zero chunks), while this deprecated one does -
# confirmed live against Bedrock. Real token streaming is a hard requirement
# here (ai-gateway/frontend depend on the "token" SSE event), so this stays
# until create_agent's streaming catches up.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langgraph.prebuilt import create_react_agent

from mcp_tools import get_mcp_tools

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
KNOWLEDGE_BASE_SSM_PARAM = os.getenv("KNOWLEDGE_BASE_SSM_PARAM", "")

SYSTEM_PROMPT = (
    "You are Ironclad, a helpful, general-purpose AI assistant. Be direct, "
    "clear, and concise - skip unnecessary preamble and get straight to the "
    "point. You may have access to tools (e.g. web search, Slack, Gmail, "
    "date/time, simple calculations) depending on configuration - use them "
    "whenever they would give a better or more current answer than your own "
    "knowledge, and say so when you do. If you're not sure about something, "
    "say so rather than guessing. When retrieved context is provided for a "
    "question, prioritize it, but fall back to your own knowledge if it "
    "doesn't actually answer the question."
)

# Bounds token growth (and cost) as a conversation gets long - the oldest
# turns just age out of what's sent to the model rather than the request
# ever failing or the caller needing to manage this themselves.
MAX_HISTORY_MESSAGES = 20


def _resolve_knowledge_base_id() -> str:
    """Looks up the knowledge base id from SSM by parameter name, rather than
    baking the id directly into the task definition - if the knowledge base
    is ever recreated, only the parameter's value changes, not this service's
    env vars. Returns "" (same as "no knowledge base configured") on any
    failure, so a broken/missing parameter degrades to plain chat instead of
    crashing the whole service at startup.
    """
    if not KNOWLEDGE_BASE_SSM_PARAM:
        return ""
    try:
        ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
        return ssm.get_parameter(Name=KNOWLEDGE_BASE_SSM_PARAM)["Parameter"]["Value"]
    except Exception:
        logger.exception(
            "Failed to resolve knowledge base id from SSM parameter %s", KNOWLEDGE_BASE_SSM_PARAM
        )
        return ""


KNOWLEDGE_BASE_ID = _resolve_knowledge_base_id()

app = FastAPI(title="Ironclad Agent")
model = ChatBedrockConverse(
    model_id=MODEL,
    region_name=os.getenv("AWS_REGION", "us-east-1"),
    streaming=True,
)
bedrock_agent_client = (
    boto3.client("bedrock-agent-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    if KNOWLEDGE_BASE_ID
    else None
)


class ChatMessage(BaseModel):
    role: str
    content: str


class InvokeRequest(BaseModel):
    message: str
    # Prior turns of this conversation, oldest first, NOT including `message`
    # itself - the frontend already keeps the full conversation in its own
    # state to render it, so "memory" is just resending that history rather
    # than the agent (or any new datastore) tracking sessions server-side.
    history: list[ChatMessage] = []


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def build_messages(history: list[ChatMessage], prompt: str) -> list[dict]:
    """Builds the full message list for the model: system prompt, the
    conversation history capped to MAX_HISTORY_MESSAGES (oldest trimmed
    first), then the current turn (`prompt`, already RAG-augmented if a
    knowledge base matched). Pure/deterministic - no LLM call - so it's
    unit-testable without hitting Bedrock, unlike the rest of run_agent.
    """
    trimmed_history = history[-MAX_HISTORY_MESSAGES:]
    return (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + [{"role": h.role, "content": h.content} for h in trimmed_history]
        + [{"role": "user", "content": prompt}]
    )


async def retrieve_context(query: str) -> tuple[list[str], list[str]]:
    """Retrieves relevant chunks (and their source filenames) from the
    knowledge base for query. Returns ([], []) if no knowledge base is
    configured - callers don't need to branch on that themselves.
    """
    if bedrock_agent_client is None:
        return [], []

    def _retrieve():
        return bedrock_agent_client.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
        )

    response = await asyncio.to_thread(_retrieve)

    chunks = []
    sources = []
    for result in response.get("retrievalResults", []):
        text = result.get("content", {}).get("text")
        if text:
            chunks.append(text)

        uri = result.get("location", {}).get("s3Location", {}).get("uri", "")
        filename = uri.rsplit("/", 1)[-1] if uri else ""
        if filename and filename not in sources:
            sources.append(filename)

    return chunks, sources


async def run_agent(message: str, history: list[ChatMessage]):
    try:
        chunks, sources = await retrieve_context(message)
        if sources:
            yield sse_event("sources", {"sources": sources})

        prompt = message
        if chunks:
            context_block = "\n\n".join(chunks)
            prompt = (
                "Use the following context to answer the question if it's relevant. "
                "If the context doesn't contain the answer, answer from your own knowledge.\n\n"
                f"Context:\n{context_block}\n\nQuestion: {message}"
            )

        tools = await get_mcp_tools()
        agent = create_react_agent(model, tools=tools)

        total_input_tokens = 0
        total_output_tokens = 0
        tool_calls = 0
        async for event in agent.astream_events(
            {"messages": build_messages(history, prompt)}, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if isinstance(content, str):
                    if content:
                        yield sse_event("token", {"text": content})
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                yield sse_event("token", {"text": text})
            elif event["event"] == "on_chat_model_end":
                usage = getattr(event["data"].get("output"), "usage_metadata", None)
                if usage:
                    total_input_tokens += usage.get("input_tokens", 0) or 0
                    total_output_tokens += usage.get("output_tokens", 0) or 0
            elif event["event"] == "on_tool_end":
                tool_calls += 1

        # ai-gateway watches for this event to enforce per-user daily token
        # limits (and, since this session, to emit its own richer usage
        # metrics/logs - model_id + tool_calls ride along for that). Doesn't
        # change anything for a client that ignores the extra fields. Token
        # counts are summed across every model call the tool-use loop made
        # this turn, not just one - a tool-calling exchange makes more than one.
        yield sse_event(
            "usage",
            {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "model_id": MODEL,
                "tool_calls": tool_calls,
            },
        )
        yield sse_event("done", {})
    except Exception as e:
        yield sse_event("error", {"message": str(e)})


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    return StreamingResponse(run_agent(req.message, req.history), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
