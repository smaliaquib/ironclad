import logging
import os
import time

import httpx
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

MCP_GATEWAY_URL = os.getenv("MCP_GATEWAY_URL", "")
_TOOLS_CACHE_TTL_SECONDS = 60

_tools_cache: list[StructuredTool] = []
_tools_fetched_at: float = 0.0


async def _call_tool(name: str, **kwargs) -> str:
    """Calls one MCP tool through the gateway's JSON-RPC endpoint and returns
    its result text - raised as an exception on any JSON-RPC/tool-side error
    so LangGraph's ToolNode reports it back to the model as a failed tool
    call, rather than silently returning error text as if it were a result.
    """
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": kwargs},
    }
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        response = await http_client.post(f"{MCP_GATEWAY_URL}/mcp", json=body)
        response.raise_for_status()
        payload = response.json()

    if "error" in payload:
        raise RuntimeError(f"{name}: {payload['error'].get('message', 'unknown error')}")

    result = payload["result"]
    text = result["content"][0]["text"]
    if result.get("isError"):
        raise RuntimeError(f"{name}: {text}")
    return text


def _make_tool_coroutine(name: str):
    """Returns a real async function bound to `name`, not a functools.partial -
    LangChain's tool-schema introspection calls inspect on the coroutine, and
    a partial object lacks the __name__/__code__ a real function has, which
    fails with "is not a module, class, method, or function" (confirmed live).
    """

    async def _tool_coroutine(**kwargs) -> str:
        return await _call_tool(name, **kwargs)

    return _tool_coroutine


async def get_mcp_tools() -> list[StructuredTool]:
    """Returns the current MCP tool catalog as LangGraph-ready tools, cached
    for _TOOLS_CACHE_TTL_SECONDS (matching the gateway's own registry cache,
    so polling faster wouldn't see anything new sooner). Returns [] if no
    gateway is configured, or if fetching/parsing the catalog fails for any
    reason - a broken or unreachable gateway degrades to "no tools" rather
    than failing the whole chat request, same philosophy as the knowledge
    base's SSM lookup.
    """
    global _tools_cache, _tools_fetched_at

    if not MCP_GATEWAY_URL:
        return []

    if _tools_cache and (time.monotonic() - _tools_fetched_at) < _TOOLS_CACHE_TTL_SECONDS:
        return _tools_cache

    try:
        async with httpx.AsyncClient(timeout=5.0) as http_client:
            response = await http_client.post(
                f"{MCP_GATEWAY_URL}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            response.raise_for_status()
            entries = response.json()["result"]["tools"]

        tools = [
            StructuredTool(
                name=entry["name"],
                description=entry["description"],
                args_schema=entry["inputSchema"],
                coroutine=_make_tool_coroutine(entry["name"]),
            )
            for entry in entries
        ]
        _tools_cache = tools
        _tools_fetched_at = time.monotonic()
        return tools
    except Exception:
        logger.exception("Failed to fetch MCP tool catalog from %s", MCP_GATEWAY_URL)
        return _tools_cache
