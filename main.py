import asyncio
import json
import os

import boto3
from anthropic import AsyncAnthropicBedrock
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")

app = FastAPI(title="Ironclad Agent")
client = AsyncAnthropicBedrock(
    aws_region=os.getenv("AWS_REGION", "us-east-1"),
)
bedrock_agent_client = (
    boto3.client("bedrock-agent-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    if KNOWLEDGE_BASE_ID
    else None
)


class InvokeRequest(BaseModel):
    message: str


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


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


async def run_agent(message: str):
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

        async with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield sse_event("token", {"text": text})
            final = await stream.get_final_message()
        # The router watches for this event to enforce per-user daily token
        # limits; it doesn't change anything for a client that ignores it.
        yield sse_event(
            "usage",
            {
                "input_tokens": final.usage.input_tokens,
                "output_tokens": final.usage.output_tokens,
            },
        )
        yield sse_event("done", {})
    except Exception as e:
        yield sse_event("error", {"message": str(e)})


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    return StreamingResponse(run_agent(req.message), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
