"""Lightweight MCP client for Monomer Bio workcells.

Communicates via JSON-RPC 2.0 over HTTP Streamable Transport (POST to /mcp).
Each session requires an initialize handshake to obtain a session ID.
"""

from __future__ import annotations

import json
import os

import requests

DEFAULT_HOST = os.getenv("WORKCELL_HOST", "192.168.68.55")
DEFAULT_PORT = int(os.getenv("WORKCELL_PORT", "8080"))


class McpClient:
    """MCP client that calls tools via HTTP Streamable Transport.

    The workcell's FastMCP server is mounted at /mcp and accepts JSON-RPC 2.0
    tool calls over HTTP POST. Each session requires an initialize handshake.

    Usage::

        client = McpClient("http://192.168.68.55:8080")
        client.connect()
        plates = client.call_tool("list_culture_plates", {})
    """

    def __init__(self, base_url: str | None = None):
        if base_url is None:
            base_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
        self.base_url = base_url
        self.mcp_url = f"{base_url}/mcp"
        self.session_id: str | None = None
        self._next_id = 1

    def _get_id(self) -> int:
        id_ = self._next_id
        self._next_id += 1
        return id_

    def connect(self) -> None:
        """Initialize the MCP session."""
        # Step 1: Initialize
        resp = requests.post(
            self.mcp_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": self._get_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "monomer-python", "version": "0.1"},
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
        self.session_id = resp.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("MCP server did not return a session ID")

        # Step 2: Send initialized notification
        requests.post(
            self.mcp_url,
            headers={
                "Content-Type": "application/json",
                "Mcp-Session-Id": self.session_id,
            },
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=10,
        )

    def call_tool(self, tool_name: str, arguments: dict, timeout: int = 30):
        """Call an MCP tool and return the parsed result.

        Handles both structuredContent and text content responses.
        Auto-connects on first call if no session exists.
        """
        if not self.session_id:
            self.connect()

        resp = requests.post(
            self.mcp_url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id,
            },
            json={
                "jsonrpc": "2.0",
                "id": self._get_id(),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            timeout=timeout,
        )
        resp.raise_for_status()

        # Parse SSE response (event: message\ndata: {...})
        body = resp.text
        for line in body.split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                result = payload.get("result", {})
                if result.get("isError"):
                    error_text = (
                        result.get("content", [{}])[0].get("text", "Unknown error")
                    )
                    raise RuntimeError(f"MCP tool error: {error_text}")

                # Prefer structuredContent, fall back to content[0].text
                sc = result.get("structuredContent", {}).get("result")
                if sc is not None:
                    return sc
                content = result.get("content", [])
                if content and content[0].get("text"):
                    try:
                        return json.loads(content[0]["text"])
                    except (json.JSONDecodeError, KeyError):
                        return content[0]["text"]
                return result

        raise RuntimeError(f"Could not parse MCP response: {body[:500]}")
