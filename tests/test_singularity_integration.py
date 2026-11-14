"""
test_singularity_integration.py — End-to-end Singularity Integration Verification.

Tests every mjx subsystem wiring point:
  OMNIBRAIN (intelligence), GHOST (agent), NEXUS (skills),
  MIRROR (memory repo), AURORA (pairing/sync), EVOLVE (metrics).
Also verifies main.py module-level imports and MJLive.__init__ attribute presence.
"""

import importlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── mjx subsystem unit smoke ─────────────────────────────────────────────────

from mjx.intelligence.brain import IntelligenceBrain, BrainOutput
from mjx.intelligence import IntentClassifier, ContextEngine, DecisionEngine, TaskPlanner
from mjx.agent import (
    DesktopAgentController, AgentRunReport, AgentSafetyGuard,
    DesktopActionPlanner, DesktopActionExecutor, DesktopExecutionVerifier,
)
from mjx.skills import SkillRegistry, SkillExecutor, SkillLoader, SkillValidator, MCPAdapter
from mjx.aurora import AuroraPairingManager, AuroraSyncProtocol
from mjx.evolution import EvolutionMetricsCollector
from mjx.security.permissions import PermissionManager, PermissionCategory


# ── 1. OMNIBRAIN Integration ─────────────────────────────────────────────────

class TestOmnibrainIntegration:
    """IntelligenceBrain processes messages and returns structured BrainOutput."""

    def test_brain_initializes_without_memory(self):
        brain = IntelligenceBrain(memory_repo=None)
        assert brain.intent_classifier is not None
        assert brain.context_engine is not None
        assert brain.decision_engine is not None
        assert brain.planner is not None
        assert brain.response_controller is not None

    def test_brain_process_simple_conversational(self):
        brain = IntelligenceBrain(memory_repo=None)
        out = brain.process_message("hello kaise ho")
        assert isinstance(out, BrainOutput)
        assert out.user_prompt == "hello kaise ho"
        assert out.intent is not None
        assert out.decision is not None
        assert out.formatted_response

    def test_brain_process_hinglish_detection(self):
        brain = IntelligenceBrain(memory_repo=None)
        out = brain.process_message("mujhe weather batao")
        assert out.intent.is_hinglish is True

    def test_brain_process_english_detection(self):
        brain = IntelligenceBrain(memory_repo=None)
        out = brain.process_message("What is the current temperature?")
        assert out.intent.is_hinglish is False

    def test_brain_emotion_parameter(self):
        brain = IntelligenceBrain(memory_repo=None)
        out = brain.process_message("I feel sad today", current_emotion="sad")
        assert isinstance(out, BrainOutput)

    def test_brain_conversation_id_threading(self):
        brain = IntelligenceBrain(memory_repo=None)
        out = brain.process_message(
            "test message",
            conversation_id="conv-test-42",
            personality_mode="casual_friend",
        )
        assert out.user_prompt == "test message"


# ── 2. GHOST Agent Integration ───────────────────────────────────────────────

class TestGhostAgentIntegration:
    """DesktopAgentController safety gates and execution pipeline."""

    def test_controller_initializes(self):
        pm = PermissionManager()
        ctrl = DesktopAgentController(permission_mgr=pm)
        assert ctrl.safety_guard is not None
        assert ctrl.perception is not None
        assert ctrl.planner is not None
        assert ctrl.executor is not None
        assert ctrl.verifier is not None

    def test_controller_blocks_without_permission(self):
        pm = PermissionManager()  # no grants
        ctrl = DesktopAgentController(permission_mgr=pm)
        report = ctrl.run_goal("open calculator")
        assert isinstance(report, AgentRunReport)
        assert report.success is False
        assert "Safety guard veto" in report.message or "blocked" in report.message.lower()

    def test_safety_guard_validates(self):
        pm = PermissionManager()
        guard = AgentSafetyGuard(pm)
        check = guard.validate_action("read_screen", "check email", "")
        assert hasattr(check, "allowed")
        assert hasattr(check, "reason")

    def test_ghost_integrated_in_desktop_action(self):
        """actions/desktop.py task path routes through GHOST agent."""
        from actions.desktop import desktop_control
        result = desktop_control({"action": "task", "task": "list files"})
        # Should hit GHOST agent and either execute or be blocked by safety
        assert isinstance(result, str)
        assert len(result) > 0


# ── 3. NEXUS Skills Integration ──────────────────────────────────────────────

class TestNexusSkillsIntegration:
    """SkillRegistry, SkillExecutor, and SkillLoader working together."""

    def test_registry_register_and_lookup(self):
        registry = SkillRegistry()
        from mjx.skills.skill_loader import SkillManifest
        manifest = SkillManifest(
            name="test_skill",
            description="A test skill for verification",
            triggers=["test", "verify"],
            permissions=[],
            folder_path=None,
        )
        ok = registry.register(manifest)
        assert ok is True
        found = registry.get_skill("test_skill")
        assert found is not None
        assert found.name == "test_skill"

    def test_registry_trigger_search(self):
        registry = SkillRegistry()
        from mjx.skills.skill_loader import SkillManifest
        manifest = SkillManifest(
            name="weather_helper",
            description="Get weather forecasts",
            triggers=["weather", "forecast"],
            permissions=[],
            folder_path=None,
        )
        registry.register(manifest)
        matches = registry.find_skills_by_trigger("weather today")
        assert len(matches) >= 1
        assert matches[0].name == "weather_helper"

    def test_registry_unregister(self):
        registry = SkillRegistry()
        from mjx.skills.skill_loader import SkillManifest
        manifest = SkillManifest(
            name="removable_skill",
            description="Will be removed",
            triggers=[],
            permissions=[],
            folder_path=None,
        )
        registry.register(manifest)
        assert registry.get_skill("removable_skill") is not None
        removed = registry.unregister("removable_skill")
        assert removed is True
        assert registry.get_skill("removable_skill") is None

    def test_executor_denies_without_permission(self):
        pm = PermissionManager()  # no grants
        executor = SkillExecutor(permission_mgr=pm)
        from mjx.skills.skill_loader import SkillManifest
        manifest = SkillManifest(
            name="restricted",
            description="Needs admin",
            triggers=[],
            permissions=["ADMIN_OPERATION"],
            folder_path=None,
        )
        result = executor.execute_skill(manifest, {})
        assert result.success is False
        assert "Permission denied" in result.error

    def test_validator_rejects_empty_name(self):
        v = SkillValidator()
        report = v.validate_metadata({"name": "", "description": "test", "permissions": []})
        assert report.is_valid is False


# ── 4. AURORA Pairing & Sync Integration ─────────────────────────────────────

class TestAuroraIntegration:
    """AuroraPairingManager and AuroraSyncProtocol."""

    def test_pairing_code_generation(self):
        mgr = AuroraPairingManager()
        session = mgr.generate_pairing_code("device-abc")
        assert len(session.pin_code) == 6
        assert session.device_id == "device-abc"
        assert session.is_authenticated is False
        assert session.token

    def test_pairing_pin_verification_success(self):
        mgr = AuroraPairingManager()
        session = mgr.generate_pairing_code("dev-1")
        token = mgr.verify_pin("dev-1", session.pin_code)
        assert token is not None
        assert mgr.is_token_valid(token) is True

    def test_pairing_pin_verification_failure(self):
        mgr = AuroraPairingManager()
        mgr.generate_pairing_code("dev-2")
        token = mgr.verify_pin("dev-2", "000000")
        # May or may not be None depending on actual pin
        # But wrong pin should fail
        # Let's use a guaranteed wrong approach
        session = mgr.generate_pairing_code("dev-3")
        wrong = str((int(session.pin_code) + 1) % 1000000).zfill(6)
        result = mgr.verify_pin("dev-3", wrong)
        assert result is None

    def test_pairing_expired_session(self):
        mgr = AuroraPairingManager(pin_ttl_secs=0.0)
        session = mgr.generate_pairing_code("dev-4")
        time.sleep(0.01)
        result = mgr.verify_pin("dev-4", session.pin_code)
        assert result is None

    def test_sync_protocol_telemetry_parsing(self):
        sync = AuroraSyncProtocol()
        raw = json.dumps({
            "device_id": "phone-1",
            "battery": 85,
            "charging": True,
            "wifi": True,
            "clipboard": "test content",
        })
        state = sync.parse_mobile_telemetry(raw)
        assert state is not None
        assert state.device_id == "phone-1"
        assert state.battery_level == 85
        assert state.is_charging is True
        assert state.clipboard_content == "test content"

    def test_sync_protocol_invalid_json(self):
        sync = AuroraSyncProtocol()
        state = sync.parse_mobile_telemetry("not json {{{")
        assert state is None

    def test_sync_push_notification(self):
        sync = AuroraSyncProtocol()
        payload = sync.build_push_notification("Alert", "Battery low", "mjx://battery")
        data = json.loads(payload)
        assert data["type"] == "notification"
        assert data["title"] == "Alert"
        assert data["body"] == "Battery low"
        assert data["action_url"] == "mjx://battery"


# ── 5. EVOLVE Metrics Integration ────────────────────────────────────────────

class TestEvolveMetricsIntegration:
    """EvolutionMetricsCollector telemetry and analytics."""

    def test_record_and_success_rate(self):
        m = EvolutionMetricsCollector()
        m.record_sample("web_search", 120.0, True)
        m.record_sample("web_search", 150.0, True)
        m.record_sample("web_search", 200.0, False, "timeout")
        rate = m.get_success_rate("web_search")
        assert abs(rate - 0.667) < 0.01

    def test_average_duration(self):
        m = EvolutionMetricsCollector()
        m.record_sample("open_app", 50.0, True)
        m.record_sample("open_app", 100.0, True)
        avg = m.get_average_duration_ms("open_app")
        assert abs(avg - 75.0) < 0.01

    def test_empty_metrics_defaults(self):
        m = EvolutionMetricsCollector()
        assert m.get_success_rate() == 1.0
        assert m.get_average_duration_ms() == 0.0

    def test_max_samples_eviction(self):
        m = EvolutionMetricsCollector(max_samples=5)
        for i in range(10):
            m.record_sample("test", float(i), True)
        assert len(m._samples) == 5

    def test_global_vs_filtered_rate(self):
        m = EvolutionMetricsCollector()
        m.record_sample("a", 10, True)
        m.record_sample("b", 10, False, "err")
        assert m.get_success_rate() == 0.5
        assert m.get_success_rate("a") == 1.0
        assert m.get_success_rate("b") == 0.0


# ── 6. MJLive Wiring Verification ────────────────────────────────────────────

class TestMJLiveWiring:
    """Verify MJLive.__init__ creates all subsystem attributes."""

    @pytest.fixture
    def mock_ui(self):
        ui = MagicMock()
        ui.muted = False
        ui.current_file = None
        return ui

    def test_mjlive_has_subsystem_attributes(self, mock_ui):
        """MJLive.__init__ should initialize all Singularity subsystems."""
        with patch("main.start_conversation", return_value="test-conv"), \
             patch("main.get_voice_interruption_enabled", return_value=True), \
             patch("main.get_emotion_settings", return_value={}), \
             patch("main.SleepInhibitor"), \
             patch("main.AutonomousLearner"), \
             patch("main.SystemMonitor"), \
             patch("main.ProactiveEngine"):
            from main import MJLive
            mj = MJLive(mock_ui)

            # Core P0-P2
            assert hasattr(mj, "emotion")
            assert hasattr(mj, "personality")

            # Singularity subsystems
            assert hasattr(mj, "permission_mgr")
            assert isinstance(mj.permission_mgr, PermissionManager)
            assert hasattr(mj, "brain")
            assert isinstance(mj.brain, IntelligenceBrain)
            assert hasattr(mj, "desktop_agent")
            assert isinstance(mj.desktop_agent, DesktopAgentController)
            assert hasattr(mj, "skill_registry")
            assert isinstance(mj.skill_registry, SkillRegistry)
            assert hasattr(mj, "skill_executor")
            assert isinstance(mj.skill_executor, SkillExecutor)
            assert hasattr(mj, "aurora_pairing")
            assert isinstance(mj.aurora_pairing, AuroraPairingManager)
            assert hasattr(mj, "aurora_sync")
            assert isinstance(mj.aurora_sync, AuroraSyncProtocol)
            assert hasattr(mj, "metrics")
            assert isinstance(mj.metrics, EvolutionMetricsCollector)


# ── 7. Tool Declaration Verification ─────────────────────────────────────────

class TestToolDeclarations:
    """Verify new tool declarations exist in TOOL_DECLARATIONS."""

    def test_runtime_metrics_tool_declared(self):
        from main import TOOL_DECLARATIONS
        names = [t["name"] for t in TOOL_DECLARATIONS]
        assert "runtime_metrics" in names

    def test_aurora_status_tool_declared(self):
        from main import TOOL_DECLARATIONS
        names = [t["name"] for t in TOOL_DECLARATIONS]
        assert "aurora_status" in names

    def test_all_core_tools_present(self):
        from main import TOOL_DECLARATIONS
        names = {t["name"] for t in TOOL_DECLARATIONS}
        core = {
            "open_app", "web_search", "system_status", "desktop_control",
            "set_emotion", "save_memory", "search_memory",
            "runtime_metrics", "aurora_status",
        }
        missing = core - names
        assert not missing, f"Missing tool declarations: {missing}"


# ── 8. Cross-Subsystem Interaction ───────────────────────────────────────────

class TestCrossSubsystemInteraction:
    """Verify subsystems can work together."""

    def test_brain_with_memory_repo(self):
        """IntelligenceBrain using actual MemoryRepository from memory_manager."""
        from memory.memory_manager import get_repository
        repo = get_repository()
        brain = IntelligenceBrain(memory_repo=repo)
        out = brain.process_message("yaad karo mera naam kya hai")
        assert isinstance(out, BrainOutput)

    def test_skill_executor_with_permission_manager(self):
        """SkillExecutor checks permissions through PermissionManager."""
        pm = PermissionManager()
        executor = SkillExecutor(permission_mgr=pm)
        from mjx.skills.skill_loader import SkillManifest
        manifest = SkillManifest(
            name="safe_skill",
            description="No special permissions",
            triggers=[],
            permissions=[],
            folder_path=None,
        )
        result = executor.execute_skill(manifest, {})
        # No permissions needed → should succeed
        assert result.success is True

    def test_metrics_after_ghost_run(self):
        """Metrics collector records GHOST agent results."""
        m = EvolutionMetricsCollector()
        pm = PermissionManager()
        ctrl = DesktopAgentController(permission_mgr=pm)
        start = time.monotonic()
        report = ctrl.run_goal("test action")
        elapsed = (time.monotonic() - start) * 1000.0
        m.record_sample(
            "desktop_control",
            elapsed,
            report.success,
            failure_reason=None if report.success else report.message[:100],
        )
        # Should have recorded exactly one sample
        assert len(m._samples) == 1
        assert m._samples[0].task_type == "desktop_control"
