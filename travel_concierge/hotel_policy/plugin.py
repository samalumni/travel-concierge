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

"""ADK plugin that injects the IHG general hotel policy into every agent's system instruction."""

from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins import BasePlugin

_POLICY_FILE = Path(__file__).parent / "general_hotel_policy.md"


class HotelPolicyPlugin(BasePlugin):
    """Injects the IHG general hotel policy into every model call across all agents."""

    def __init__(self) -> None:
        super().__init__(name="hotel_policy")
        self._policy_text: str = _POLICY_FILE.read_text(encoding="utf-8")

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        """Append the hotel policy to the system instruction before each model call."""
        llm_request.append_instructions([self._policy_text])
        return None
