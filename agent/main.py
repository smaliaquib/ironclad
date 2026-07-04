import json
import os

from anthropic import AsyncAnthropicBedrock
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

MODEL = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

app = FastAPI(title="Ironclad Agent")
client = AsyncAnthropicBedrock(
    aws_region=os.getenv("AWS_REGION", "us-east-1"),
)


class InvokeRequest(BaseModel):
    message: str


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_agent(message: str):
    try:
        async with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": message}],
        ) as stream:
            async for text in stream.text_stream:
                yield sse_event("token", {"text": text})
        yield sse_event("done", {})
    except Exception as e:
        yield sse_event("error", {"message": str(e)})


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    return StreamingResponse(run_agent(req.message), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
