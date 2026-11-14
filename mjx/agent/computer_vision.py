"""
mjx.agent.computer_vision — Screen Perception and Coordinate Normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class UIElementBox:
    element_id: str
    label: str
    norm_x: int  # 0 to 1000
    norm_y: int  # 0 to 1000
    norm_w: int  # 0 to 1000
    norm_h: int  # 0 to 1000
    confidence: float = 0.9

    def center_norm(self) -> Tuple[int, int]:
        return (self.norm_x + self.norm_w // 2, self.norm_y + self.norm_h // 2)


class DesktopPerception:
    """Manages coordinate normalization and visual element targeting."""

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = max(640, screen_width)
        self.screen_height = max(480, screen_height)

    def set_screen_resolution(self, width: int, height: int) -> None:
        self.screen_width = max(640, width)
        self.screen_height = max(480, height)

    def norm_to_pixel(self, norm_x: int, norm_y: int) -> Tuple[int, int]:
        """Converts 0-1000 normalized coordinates to actual display pixels."""
        clamped_x = max(0, min(1000, norm_x))
        clamped_y = max(0, min(1000, norm_y))
        px = int(clamped_x * self.screen_width / 1000.0)
        py = int(clamped_y * self.screen_height / 1000.0)
        return (px, py)

    def pixel_to_norm(self, px: int, py: int) -> Tuple[int, int]:
        """Converts display pixels to 0-1000 normalized coordinates."""
        norm_x = int(max(0, min(self.screen_width, px)) * 1000.0 / self.screen_width)
        norm_y = int(max(0, min(self.screen_height, py)) * 1000.0 / self.screen_height)
        return (norm_x, norm_y)

    def find_best_element(self, query: str, elements: List[UIElementBox]) -> Optional[UIElementBox]:
        """Finds closest matching UI element by label."""
        query_norm = query.lower().strip()
        if not query_norm or not elements:
            return None

        # Exact match first
        for el in elements:
            if el.label.lower().strip() == query_norm:
                return el

        # Partial substring match
        for el in elements:
            if query_norm in el.label.lower():
                return el

        return None
