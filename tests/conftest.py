"""Pytest configuration file for tests."""

import sys
from unittest.mock import MagicMock

# Mock google.auth.default BEFORE any code tries to import travel_concierge
mock_credentials = MagicMock()


class MockDefaultAuth:
    def default(self):
        return (mock_credentials, "test-project-id")


sys.modules["google.auth.default"] = MockDefaultAuth()

# Now patch google.auth module itself
import google.auth
google.auth.default = lambda: (mock_credentials, "test-project-id")
