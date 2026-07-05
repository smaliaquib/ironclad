import asyncio

import pytest

import mcp_tools


@pytest.fixture(autouse=True)
def reset_cache():
    mcp_tools._tools_cache = []
    mcp_tools._tools_fetched_at = 0.0
    yield
    mcp_tools._tools_cache = []
    mcp_tools._tools_fetched_at = 0.0


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, payload=None, error=None, **kwargs):
        self._payload = payload
        self._error = error
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        self.requests.append((url, json))
        if self._error:
            raise self._error
        return FakeResponse(self._payload)


TOOLS_LIST_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {
                "name": "echo",
                "description": "Echoes back the provided message.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            }
        ]
    },
}


def test_returns_empty_without_gateway_url(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "")

    assert asyncio.run(mcp_tools.get_mcp_tools()) == []


def test_builds_structured_tools_from_registry(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    monkeypatch.setattr(
        mcp_tools.httpx, "AsyncClient", lambda **kw: FakeAsyncClient(payload=TOOLS_LIST_PAYLOAD)
    )

    tools = asyncio.run(mcp_tools.get_mcp_tools())

    assert len(tools) == 1
    assert tools[0].name == "echo"
    assert tools[0].description == "Echoes back the provided message."
    assert tools[0].args_schema["required"] == ["message"]


def test_returns_empty_on_fetch_failure_with_no_prior_cache(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    monkeypatch.setattr(
        mcp_tools.httpx, "AsyncClient", lambda **kw: FakeAsyncClient(error=RuntimeError("boom"))
    )

    assert asyncio.run(mcp_tools.get_mcp_tools()) == []


def test_returns_last_known_good_cache_on_later_failure(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    monkeypatch.setattr(
        mcp_tools.httpx, "AsyncClient", lambda **kw: FakeAsyncClient(payload=TOOLS_LIST_PAYLOAD)
    )
    first = asyncio.run(mcp_tools.get_mcp_tools())
    assert len(first) == 1

    # Force the cache to look stale, then simulate the gateway going down.
    mcp_tools._tools_fetched_at = 0.0
    monkeypatch.setattr(
        mcp_tools.httpx, "AsyncClient", lambda **kw: FakeAsyncClient(error=RuntimeError("down"))
    )

    second = asyncio.run(mcp_tools.get_mcp_tools())
    assert second == first


def test_call_tool_posts_expected_body_and_returns_text(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    fake_client = FakeAsyncClient(
        payload={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": '{"echoed": "hi"}'}]},
        }
    )
    monkeypatch.setattr(mcp_tools.httpx, "AsyncClient", lambda **kw: fake_client)

    result = asyncio.run(mcp_tools._call_tool("echo", message="hi"))

    assert result == '{"echoed": "hi"}'
    url, body = fake_client.requests[0]
    assert url == "http://mcp-gateway.local:9000/mcp"
    assert body["method"] == "tools/call"
    assert body["params"] == {"name": "echo", "arguments": {"message": "hi"}}


def test_call_tool_raises_on_is_error_result(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    monkeypatch.setattr(
        mcp_tools.httpx,
        "AsyncClient",
        lambda **kw: FakeAsyncClient(
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"content": [{"type": "text", "text": "boom"}], "isError": True},
            }
        ),
    )

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(mcp_tools._call_tool("echo", message="hi"))


def test_call_tool_raises_on_jsonrpc_error(monkeypatch):
    monkeypatch.setattr(mcp_tools, "MCP_GATEWAY_URL", "http://mcp-gateway.local:9000")
    monkeypatch.setattr(
        mcp_tools.httpx,
        "AsyncClient",
        lambda **kw: FakeAsyncClient(
            payload={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32601, "message": "unknown tool"},
            }
        ),
    )

    with pytest.raises(RuntimeError, match="unknown tool"):
        asyncio.run(mcp_tools._call_tool("bogus", message="hi"))
