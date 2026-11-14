"""
mjx.intelligence.reflection — Task Outcome Evaluation and Failure Analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FailureType(str, Enum):
    NONE = "none"
    PERMISSION_DENIED = "permission_denied"
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    PARAM_MISMATCH = "param_mismatch"
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"
    UNEXPECTED = "unexpected"


@dataclass
class ReflectionReport:
    success: bool
    failure_type: FailureType
    summary: str
    suggested_alternative: Optional[str] = None


class TaskReflectionEngine:
    """Evaluates task execution outcomes without unverified assumptions."""

    def evaluate(self, goal: str, action: str, returncode: int, stdout: str, stderr: str) -> ReflectionReport:
        if returncode == 0:
            return ReflectionReport(
                success=True,
                failure_type=FailureType.NONE,
                summary=f"Action '{action}' completed successfully.",
            )

        err_lower = (stderr or stdout).lower()

        if "permission" in err_lower or "denied" in err_lower or "blocked" in err_lower:
            return ReflectionReport(
                success=False,
                failure_type=FailureType.PERMISSION_DENIED,
                summary=f"Action '{action}' was blocked by user permissions.",
                suggested_alternative="Request explicit permission from user before retrying.",
            )

        if "timed out" in err_lower or "timeout" in err_lower:
            return ReflectionReport(
                success=False,
                failure_type=FailureType.TIMEOUT,
                summary=f"Action '{action}' exceeded maximum execution timeout.",
                suggested_alternative="Verify network or reduce task workload.",
            )

        if "not found" in err_lower or "cannot find" in err_lower:
            return ReflectionReport(
                success=False,
                failure_type=FailureType.TOOL_ERROR,
                summary=f"Target binary or parameter for '{action}' was not found.",
                suggested_alternative="Check application path or installed tools.",
            )

        return ReflectionReport(
            success=False,
            failure_type=FailureType.UNEXPECTED,
            summary=f"Action '{action}' returned error code {returncode}: {stderr[:150]}",
            suggested_alternative="Report error clearly to user.",
        )
