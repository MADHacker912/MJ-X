"""
mjx.live.error_classifier — Classification of Live WebSocket Exceptions.
"""

from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Optional, Tuple
from mjx.live.connection_state import ErrorCategory


@dataclass
class ClassifiedError:
    category: ErrorCategory
    close_code: Optional[int]
    message: str
    is_recoverable: bool
    underlying_exception: BaseException


class LiveSessionRecoveryRequired(Exception):
    """Signals that the current WebSocket session terminated recoverably and must be reconnected."""
    def __init__(self, classified: ClassifiedError):
        self.classified = classified
        super().__init__(f"LiveSessionRecoveryRequired: {classified.category.value} (code={classified.close_code}): {classified.message}")


class LiveErrorClassifier:
    """Classifies exceptions from the Gemini Live stream to drive recovery decisions."""

    RECOVERABLE_CODES = {1006, 1011, 1012, 1013, 500, 502, 503, 504}
    AUTH_CODES = {1007, 401, 403}
    NORMAL_CODES = {1000, 1001}

    @classmethod
    def classify(cls, exc: BaseException) -> ClassifiedError:
        # Unwrap ExceptionGroup if present (Python 3.11+)
        unwrapped = cls._unwrap_exception_group(exc)

        # Directly return pre-classified recovery signal
        if isinstance(unwrapped, LiveSessionRecoveryRequired):
            return unwrapped.classified
        
        # Check for explicit cancellation
        if isinstance(unwrapped, asyncio.CancelledError):
            return ClassifiedError(
                category=ErrorCategory.NORMAL_CLOSURE,
                close_code=1000,
                message="Task cancelled",
                is_recoverable=False,
                underlying_exception=unwrapped,
            )

        err_str = str(unwrapped)
        code = cls._extract_code(unwrapped)

        # 1. Authentication / Permission errors (Non-recoverable without new key)
        if (
            code in cls.AUTH_CODES
            or "API key not valid" in err_str
            or "PERMISSION_DENIED" in err_str
            or "UNAUTHENTICATED" in err_str
        ):
            return ClassifiedError(
                category=ErrorCategory.AUTHENTICATION_ERROR,
                close_code=code or 1007,
                message=cls._sanitize_message(err_str),
                is_recoverable=False,
                underlying_exception=unwrapped,
            )

        # 2. Configuration / Bad request errors
        if (
            code == 400
            or "INVALID_ARGUMENT" in err_str
            or "NOT_FOUND" in err_str
            or "Resource has been exhausted" in err_str and "quota" in err_str.lower()
        ):
            return ClassifiedError(
                category=ErrorCategory.CONFIGURATION_ERROR,
                close_code=code or 400,
                message=cls._sanitize_message(err_str),
                is_recoverable=False,
                underlying_exception=unwrapped,
            )

        # 3. Programming errors — genuine application bugs (Must NOT be silently swallowed)
        if isinstance(
            unwrapped,
            (
                TypeError,
                AttributeError,
                NameError,
                SyntaxError,
                KeyError,
                IndexError,
                ZeroDivisionError,
                ArithmeticError,
                ValueError,
                AssertionError,
                NotImplementedError,
                ImportError,
                UnboundLocalError,
            ),
        ):
            return ClassifiedError(
                category=ErrorCategory.PROGRAMMING_ERROR,
                close_code=None,
                message=cls._sanitize_message(err_str),
                is_recoverable=False,
                underlying_exception=unwrapped,
            )

        # 4. Normal closure
        if code in cls.NORMAL_CODES or "normal close" in err_str.lower():
            return ClassifiedError(
                category=ErrorCategory.NORMAL_CLOSURE,
                close_code=code or 1000,
                message=cls._sanitize_message(err_str),
                is_recoverable=False,
                underlying_exception=unwrapped,
            )

        # 5. Transient server errors — 1011 Internal Error, 503, 500, etc.
        if (
            code in cls.RECOVERABLE_CODES
            or "1011" in err_str
            or "internal error" in err_str.lower()
            or "server error" in err_str.lower()
            or "service unavailable" in err_str.lower()
        ):
            return ClassifiedError(
                category=ErrorCategory.TRANSIENT_SERVER_ERROR,
                close_code=code or 1011,
                message=cls._sanitize_message(err_str),
                is_recoverable=True,
                underlying_exception=unwrapped,
            )

        # 6. Network / Transport errors
        net_markers = (
            "TimeoutError", "timed out", "getaddrinfo", "ConnectionRefusedError",
            "ConnectionResetError", "BrokenPipeError", "OSError", "Cannot connect",
            "1006", "closed without close frame",
        )
        if any(marker in err_str for marker in net_markers) or isinstance(
            unwrapped, (asyncio.TimeoutError, ConnectionError, OSError)
        ):
            return ClassifiedError(
                category=ErrorCategory.NETWORK_ERROR,
                close_code=code or 1006,
                message=cls._sanitize_message(err_str),
                is_recoverable=True,
                underlying_exception=unwrapped,
            )

        # Default fallback for unclassified exceptions
        return ClassifiedError(
            category=ErrorCategory.TRANSIENT_SERVER_ERROR,
            close_code=code,
            message=cls._sanitize_message(err_str),
            is_recoverable=True,
            underlying_exception=unwrapped,
        )

    @classmethod
    def _unwrap_exception_group(cls, exc: BaseException) -> BaseException:
        """Extract the most significant exception from an ExceptionGroup."""
        if hasattr(exc, "exceptions") and exc.exceptions:
            for sub_exc in exc.exceptions:
                # Prioritize APIError or non-CancelledError
                if not isinstance(sub_exc, asyncio.CancelledError):
                    return cls._unwrap_exception_group(sub_exc)
            return exc.exceptions[0]
        return exc

    @classmethod
    def _extract_code(cls, exc: BaseException) -> Optional[int]:
        """Inspect common code attributes on APIError or WebSocket exceptions."""
        if hasattr(exc, "code") and exc.code is not None:
            try:
                return int(exc.code)
            except (ValueError, TypeError):
                pass
        
        # Check rcvd on websockets.exceptions.ConnectionClosed
        rcvd = getattr(exc, "rcvd", None)
        if rcvd and hasattr(rcvd, "code") and rcvd.code is not None:
            try:
                return int(rcvd.code)
            except (ValueError, TypeError):
                pass

        # String inspection fallback for code numbers
        for candidate in (1011, 1006, 1007, 1000, 1001, 1012, 1013, 401, 403, 400, 500, 503):
            if str(candidate) in str(exc):
                return candidate
        return None

    @classmethod
    def _sanitize_message(cls, msg: str) -> str:
        """Strip sensitive token substrings and limit message length for privacy-safe logs."""
        import re
        sanitized = re.sub(r"AIza[0-9A-Za-z_-]{30,}", "[REDACTED_API_KEY]", msg)
        sanitized = re.sub(r"key=[0-9A-Za-z_-]{10,}", "key=[REDACTED]", sanitized)
        return sanitized[:200]
