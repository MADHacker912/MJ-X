"""
mjx.evolution.proposals — Non-Self-Modifying Self-Improvement Proposals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from mjx.evolution.metrics import EvolutionMetricsCollector


@dataclass
class ImprovementProposal:
    proposal_id: str
    target_subsystem: str
    rationale: str
    proposed_change: str
    requires_user_approval: bool = True
    status: str = "PENDING"  # "PENDING", "APPROVED", "REJECTED"
    created_at: float = field(default_factory=time.time)


class EvolutionProposalEngine:
    """Analyzes telemetry patterns and proposes non-self-modifying configuration optimizations."""

    def __init__(self, metrics: EvolutionMetricsCollector):
        self.metrics = metrics
        self._proposals: List[ImprovementProposal] = []

    def evaluate_and_propose(self) -> List[ImprovementProposal]:
        proposals: List[ImprovementProposal] = []

        # Check for slow tasks
        avg_dur = self.metrics.get_average_duration_ms()
        if avg_dur > 2000.0:
            p = ImprovementProposal(
                proposal_id=f"opt_timeout_{int(time.time())}",
                target_subsystem="agent_executor",
                rationale=f"Average task duration ({avg_dur}ms) exceeds 2000ms target threshold",
                proposed_change="Increase pre-fetch concurrency and adjust sleep polling interval to 0.05s",
            )
            proposals.append(p)

        # Check for failing tasks
        success_rate = self.metrics.get_success_rate()
        if success_rate < 0.85:
            p = ImprovementProposal(
                proposal_id=f"opt_retry_{int(time.time())}",
                target_subsystem="planner",
                rationale=f"Global task success rate ({success_rate * 100:.1f}%) is below 85% SLA",
                proposed_change="Enable 1x automatic reflection retry for timeout and permission errors",
            )
            proposals.append(p)

        self._proposals.extend(proposals)
        return proposals

    def get_pending_proposals(self) -> List[ImprovementProposal]:
        return [p for p in self._proposals if p.status == "PENDING"]
