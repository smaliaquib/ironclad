import asyncio

import main


class FakeBedrockAgentClient:
    def __init__(self, response):
        self._response = response

    def retrieve(self, **kwargs):
        return self._response


def test_retrieve_context_returns_empty_without_knowledge_base(monkeypatch):
    monkeypatch.setattr(main, "bedrock_agent_client", None)

    chunks, sources = asyncio.run(main.retrieve_context("hello"))

    assert chunks == []
    assert sources == []


def test_retrieve_context_parses_chunks_and_deduplicated_sources(monkeypatch):
    fake_response = {
        "retrievalResults": [
            {
                "content": {"text": "chunk one"},
                "location": {"s3Location": {"uri": "s3://bucket/docs/a.pdf"}},
            },
            {
                "content": {"text": "chunk two"},
                "location": {"s3Location": {"uri": "s3://bucket/docs/a.pdf"}},
            },
            {
                "content": {"text": "chunk three"},
                "location": {"s3Location": {"uri": "s3://bucket/docs/b.txt"}},
            },
        ]
    }
    monkeypatch.setattr(main, "bedrock_agent_client", FakeBedrockAgentClient(fake_response))
    monkeypatch.setattr(main, "KNOWLEDGE_BASE_ID", "kb-123")

    chunks, sources = asyncio.run(main.retrieve_context("hello"))

    assert chunks == ["chunk one", "chunk two", "chunk three"]
    assert sources == ["a.pdf", "b.txt"]
