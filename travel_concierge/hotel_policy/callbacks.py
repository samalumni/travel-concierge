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

"""Per-agent before_model_callbacks that inject agent-specific hotel policies.

Design:
  - Each function has a single responsibility: inject the policy for its
    designated agent domain.
  - Functions are plain async callables matching ADK's BeforeModelCallback
    protocol — Agent depends on the protocol, not on this module directly.
  - Sub-agents in the same domain share their parent domain's callback
    (e.g. place_agent and poi_agent both use inspiration_policy_callback).
  - All functions return None so they never short-circuit the ADK flow.

Execution order (ADK):
  HotelPolicyPlugin.before_model_callback  (general policy, runs first)
      └── <this callback>                  (agent-specific policy, runs second)
"""

from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    return (_DIR / filename).read_text(encoding="utf-8")


# Load each policy file once at import time.
_ROOT_POLICY         = _load("root_agent.md")
_INSPIRATION_POLICY  = _load("inspiration_agent.md")
_PLANNING_POLICY     = _load("planning_agent.md")
_BOOKING_POLICY      = _load("booking_agent.md")
_PRE_TRIP_POLICY     = _load("pre_trip_agent.md")
_IN_TRIP_POLICY      = _load("in_trip_agent.md")
_POST_TRIP_POLICY    = _load("post_trip_agent.md")


# ── Callback functions ────────────────────────────────────────────────────────
# One function per policy domain.  Sub-agents within a domain reuse their
# parent's callback — wired at the Agent definition, not here.

async def root_agent_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject root_agent hotel policy into the system instruction."""
    llm_request.append_instructions([_ROOT_POLICY])
    return None


async def inspiration_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject inspiration-domain hotel policy (inspiration_agent, place_agent, poi_agent)."""
    llm_request.append_instructions([_INSPIRATION_POLICY])
    return None


async def planning_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject planning-domain hotel policy (planning_agent, hotel_search_agent,
    hotel_room_selection_agent, itinerary_agent)."""
    llm_request.append_instructions([_PLANNING_POLICY])
    return None


async def booking_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject booking-domain hotel policy (booking_agent, create_reservation,
    payment_choice, process_payment)."""
    llm_request.append_instructions([_BOOKING_POLICY])
    return None


async def pre_trip_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject pre-trip hotel policy (pre_trip_agent, what_to_pack_agent)."""
    llm_request.append_instructions([_PRE_TRIP_POLICY])
    return None


async def in_trip_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject in-trip hotel policy (in_trip_agent, day_of_agent, trip_monitor_agent)."""
    llm_request.append_instructions([_IN_TRIP_POLICY])
    return None


async def post_trip_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    """Inject post-trip hotel policy (post_trip_agent)."""
    llm_request.append_instructions([_POST_TRIP_POLICY])
    return None
