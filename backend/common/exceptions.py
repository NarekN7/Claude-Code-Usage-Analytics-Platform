"""
Application-level exceptions.

Raises:
    AppException: Base class for recoverable application errors.
"""

from __future__ import annotations


class AppException(Exception):
    """
    Base exception for application-level errors exposed to API callers.

    Args:
        message (str): Human-readable error description.
        status_code (int): Suggested HTTP status code when raised from a route.

    Attributes:
        message (str): Error message.
        status_code (int): HTTP status code hint.
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """
        Initialize AppException.

        Args:
            message (str): Description of the error.
            status_code (int): HTTP status code for API responses.

        Returns:
            None
        """
        self.message = message
        self.status_code = status_code
        super().__init__(message)
