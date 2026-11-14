"""
mjx.evolution — Telemetry and Non-Self-Modifying Self-Improvement (Project EVOLVE).
"""

from mjx.evolution.metrics import EvolutionMetricsCollector, TaskMetricSample
from mjx.evolution.proposals import EvolutionProposalEngine, ImprovementProposal

__all__ = [
    "EvolutionMetricsCollector",
    "TaskMetricSample",
    "EvolutionProposalEngine",
    "ImprovementProposal",
]
