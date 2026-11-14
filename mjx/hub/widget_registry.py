"""
mjx.hub.widget_registry — Visual Workspace Widget Definitions and Schemas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VisualWidget:
    widget_id: str
    widget_type: str  # "status_card", "timeline", "metric_gauge", "memory_viewer"
    title: str
    data: Dict[str, Any]
    last_updated: float = field(default_factory=time.time)


class WidgetRegistry:
    """Manages active visual cards and workspace widgets for PyQt6 and Web Dashboard."""

    def __init__(self):
        self._widgets: Dict[str, VisualWidget] = {}

    def update_or_create(self, widget_id: str, widget_type: str, title: str, data: Dict[str, Any]) -> VisualWidget:
        widget = VisualWidget(
            widget_id=widget_id,
            widget_type=widget_type,
            title=title,
            data=data,
            last_updated=time.time(),
        )
        self._widgets[widget_id] = widget
        return widget

    def get_widget(self, widget_id: str) -> Optional[VisualWidget]:
        return self._widgets.get(widget_id)

    def list_widgets(self) -> List[VisualWidget]:
        return sorted(self._widgets.values(), key=lambda w: w.last_updated, reverse=True)

    def remove_widget(self, widget_id: str) -> bool:
        return self._widgets.pop(widget_id, None) is not None
