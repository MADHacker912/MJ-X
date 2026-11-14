"""
mjx.skills.mcp_adapter — Model Context Protocol (MCP) Bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPAdapter:
    """Adapts Model Context Protocol tools into MJ-X compatible calling interfaces."""

    def __init__(self):
        self._registered_tools: Dict[str, MCPToolDefinition] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register_mcp_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        tool_def = MCPToolDefinition(name=name, description=description, input_schema=input_schema)
        self._registered_tools[name] = tool_def
        if handler:
            self._handlers[name] = handler

    def to_gemini_tool_declaration(self, tool_name: str) -> Optional[Dict[str, Any]]:
        tool = self._registered_tools.get(tool_name)
        if not tool:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        }

    def dispatch_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self._registered_tools:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}

        handler = self._handlers.get(tool_name)
        if not handler:
            return {"success": False, "error": f"No handler registered for '{tool_name}'"}

        try:
            result = handler(arguments)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": f"Handler error: {e}"}
