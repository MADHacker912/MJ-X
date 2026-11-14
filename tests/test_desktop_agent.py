"""
tests.test_desktop_agent — Unit tests for mjx.agent (Project GHOST).
"""

import pytest

from mjx.agent import (
    DesktopAgentController,
    AgentSafetyGuard,
    DesktopPerception,
    DesktopActionPlanner,
    ActionPrimitive,
    DesktopActionExecutor,
    DesktopExecutionVerifier,
    UIElementBox,
)
from mjx.security.permissions import PermissionCategory, PermissionManager


def test_desktop_perception_coordinate_conversion():
    perc = DesktopPerception(screen_width=1920, screen_height=1080)

    # Center norm (500, 500) -> (960, 540)
    px, py = perc.norm_to_pixel(500, 500)
    assert px == 960
    assert py == 540

    # Roundtrip conversion
    nx, ny = perc.pixel_to_norm(px, py)
    assert nx == 500
    assert ny == 500

    # Element lookup
    el1 = UIElementBox("el1", "Submit Button", 100, 200, 50, 20)
    el2 = UIElementBox("el2", "Cancel Button", 200, 200, 50, 20)
    matched = perc.find_best_element("submit", [el1, el2])
    assert matched is not None
    assert matched.element_id == "el1"


def test_agent_safety_guard_blocks_sensitive_windows_and_commands():
    perm = PermissionManager()
    guard = AgentSafetyGuard(perm)

    # Destructive command
    res1 = guard.validate_action("type", target_description="rm -rf /")
    assert res1.allowed is False
    assert res1.risk_level == "CRITICAL"

    # Sensitive window
    res2 = guard.validate_action("click", window_title="Bank Login - Chrome")
    assert res2.allowed is False
    assert res2.risk_level == "HIGH"

    # Emergency stop
    perm.emergency_stop()
    res3 = guard.validate_action("click", target_description="Click OK")
    assert res3.allowed is False
    assert "Emergency Stop" in res3.reason


def test_desktop_action_planner_search_workflow():
    planner = DesktopActionPlanner()

    steps = planner.plan_steps_for_intent("search for weather in Delhi")
    assert len(steps) == 3
    assert steps[0].primitive == ActionPrimitive.CLICK
    assert steps[1].primitive == ActionPrimitive.TYPE_TEXT
    assert "weather in delhi" in steps[1].text_payload.lower()
    assert steps[2].primitive == ActionPrimitive.PRESS_KEY


def test_desktop_agent_controller_end_to_end_custom_dispatcher():
    dispatched = []

    def mock_dispatcher(step, x, y):
        dispatched.append((step.primitive.value, x, y))
        return True

    perm = PermissionManager()
    # Grant OS_INPUT_CONTROL
    perm.grant(PermissionCategory.OS_INPUT_CONTROL, duration_seconds=60.0)

    controller = DesktopAgentController(
        permission_mgr=perm,
        custom_dispatcher=mock_dispatcher,
        screen_width=1920,
        screen_height=1080,
    )

    report = controller.run_goal("click on Save")
    assert report.success is True
    assert report.steps_executed == 1
    assert len(dispatched) == 1
    assert dispatched[0][0] == "click"
