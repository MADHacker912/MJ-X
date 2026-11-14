"""
tests.test_evolution — Unit tests for mjx.evolution (Project EVOLVE).
"""

from mjx.evolution import EvolutionMetricsCollector, EvolutionProposalEngine


def test_evolution_metrics_and_proposals():
    collector = EvolutionMetricsCollector()

    # Record some fast successes
    collector.record_sample("web_search", duration_ms=450.0, success=True)
    collector.record_sample("web_search", duration_ms=550.0, success=True)

    assert collector.get_success_rate("web_search") == 1.0
    assert collector.get_average_duration_ms("web_search") == 500.0

    # Record failures and slow runs to trigger proposals
    collector.record_sample("heavy_task", duration_ms=3500.0, success=False, failure_reason="timeout")
    collector.record_sample("heavy_task", duration_ms=3200.0, success=False, failure_reason="timeout")

    engine = EvolutionProposalEngine(collector)
    props = engine.evaluate_and_propose()

    # Should have proposals due to low success rate and high duration
    assert len(props) >= 1
    assert any(p.target_subsystem in {"planner", "agent_executor"} for p in props)
    assert all(p.requires_user_approval is True for p in props)
