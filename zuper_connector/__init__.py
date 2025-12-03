"""
Zuper API Connector

A Python connector for the Zuper Field Service Management API.
"""

from .client import ZuperClient
from .exceptions import ZuperAPIError, ZuperAuthError, ZuperRateLimitError

__version__ = "0.1.0"
__all__ = ["ZuperClient", "ZuperAPIError", "ZuperAuthError", "ZuperRateLimitError"]
