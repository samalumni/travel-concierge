# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ADK plugin that injects the IHG general hotel policy into every agent's
system instruction.

Design responsibility: cross-cutting, application-wide policy only.
Agent-specific policies are injected via per-agent before_model_callbacks
defined in hotel_policy/callbacks.py and wired directly to each Agent.

Execution order (from ADK internals):
  1. This plugin's before_model_callback runs first (all agents).
  2. Each agent's own before_model_callback runs next (specific agent only).
Both modify LlmRequest in sequence; this plugin always returns None so it
never short-circuits the agent-level callbacks.
"""

from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin

_GENERAL_POLICY_FILE = Path(__file__).parent / "general_hotel_policy.md"


class HotelPolicyPlugin(BasePlugin):
    """Appends the IHG general hotel policy to every model call across all agents.

    Single responsibility: inject general_hotel_policy.md globally.
    Agent-specific policies are the responsibility of per-agent callbacks
    in hotel_policy/callbacks.py.
    """

    def __init__(self) -> None:
        super().__init__(name="hotel_policy")
        self._general_policy: str = _GENERAL_POLICY_FILE.read_text(encoding="utf-8")

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        """Append the general hotel policy to the system instruction.

        Always returns None so the agent-level before_model_callback
        is never short-circuited.
        """
        llm_request.append_instructions([self._general_policy])
        return None

