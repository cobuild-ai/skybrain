"""Tests for SkyBrain Model Context Protocol (MCP) Server."""

import pytest
import json
from unittest.mock import AsyncMock
from skybrain.mcp.server import SkyBrainMCPServer, TOOLS


@pytest.mark.asyncio
async def test_mcp_initialize():
    server = SkyBrainMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = await server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "protocolVersion" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "skybrain"


@pytest.mark.asyncio
async def test_mcp_tools_list():
    server = SkyBrainMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = await server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "skybrain_expert_consensus" in tool_names
    assert "skybrain_query" in tool_names
    assert "skybrain_translate" in tool_names
    assert "skybrain_summarize_logs" in tool_names


@pytest.mark.asyncio
async def test_mcp_tools_call_translate():
    server = SkyBrainMCPServer()
    # Mock client.query
    server.client.query = AsyncMock(return_value="Hello World")
    
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "skybrain_translate",
            "arguments": {
                "text": "안녕하세요",
                "target_lang": "EN"
            }
        }
    }
    resp = await server.handle_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 3
    content = resp["result"]["content"][0]["text"]
    assert "Hello World" in content


@pytest.mark.asyncio
async def test_mcp_unknown_method():
    server = SkyBrainMCPServer()
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "unknown_rpc_method"
    }
    resp = await server.handle_request(req)
    assert resp["error"]["code"] == -32601
