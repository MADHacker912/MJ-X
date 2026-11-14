"""
mjx.hub.hub_controller — Real-time Visual Hub Orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from mjx.hub.widget_registry import VisualWidget, WidgetRegistry


class VisualHubController:
    """Dispatches synchronized UI state and visual workspace events."""

    def __init__(self):
        self.registry = WidgetRegistry()
        self._subscribers: List[Callable[[VisualWidget], None]] = []

    def subscribe(self, callback: Callable[[VisualWidget], None]) -> None:
        self._subscribers.append(callback)

    def publish_widget_update(
        self,
        widget_id: str,
        widget_type: str,
        title: str,
        data: Dict[str, Any],
    ) -> VisualWidget:
        widget = self.registry.update_or_create(widget_id, widget_type, title, data)
        for sub in self._subscribers:
            try:
                sub(widget)
            except Exception:
                pass
        return widget

    def get_workspace_snapshot(self) -> Dict[str, Any]:
        return {
            "widgets": [
                {
                    "id": w.widget_id,
                    "type": w.widget_type,
                    "title": w.title,
                    "data": w.data,
                    "updated_at": w.last_updated,
                }
                for w in self.registry.list_widgets()
            ]
        }
