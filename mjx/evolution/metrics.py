"""
mjx.evolution.metrics — Telemetry, Failure Rate Tracking, and Reliability Metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaskMetricSample:
    task_type: str
    duration_ms: float
    success: bool
    failure_reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class EvolutionMetricsCollector:
    """Collects runtime telemetry to guide deterministic system improvements."""

    def __init__(self, max_samples: int = 500):
        self.max_samples = max_samples
        self._samples: List[TaskMetricSample] = []

    def record_sample(
        self,
        task_type: str,
        duration_ms: float,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> None:
        sample = TaskMetricSample(
            task_type=task_type,
            duration_ms=duration_ms,
            success=success,
            failure_reason=failure_reason,
            timestamp=time.time(),
        )
        self._samples.append(sample)
        if len(self._samples) > self.max_samples:
            self._samples.pop(0)

    def get_success_rate(self, task_type: Optional[str] = None) -> float:
        filtered = [s for s in self._samples if task_type is None or s.task_type == task_type]
        if not filtered:
            return 1.0
        successes = sum(1 for s in filtered if s.success)
        return round(successes / len(filtered), 3)

    def get_average_duration_ms(self, task_type: Optional[str] = None) -> float:
        filtered = [s for s in self._samples if task_type is None or s.task_type == task_type]
        if not filtered:
            return 0.0
        return round(sum(s.duration_ms for s in filtered) / len(filtered), 2)
