"""Per-agent before_model_callbacks that inject agent-specific hotel policies.

Design:
  - Each function injects the policy for its designated agent domain.
  - Functions match ADK's BeforeModelCallback protocol and return None.
  - Sub-agents in the same domain share their parent's callback.

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


_ROOT_POLICY            = _load("root_agent.md")
_PRE_STAY_POLICY        = _load("pre_stay_agent.md")
_IN_STAY_POLICY         = _load("in_stay_agent.md")
_POST_STAY_POLICY       = _load("post_stay_agent.md")
_DINING_POLICY          = _load("dining_agent.md")
_HOUSEKEEPING_POLICY    = _load("housekeeping_agent.md")
_LOCAL_CONCIERGE_POLICY = _load("local_concierge_agent.md")
_STAY_MONITOR_POLICY    = _load("stay_monitor_agent.md")


async def root_agent_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_ROOT_POLICY])
    return None


async def pre_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_PRE_STAY_POLICY])
    return None


async def in_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_IN_STAY_POLICY])
    return None


async def post_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_POST_STAY_POLICY])
    return None


async def dining_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_DINING_POLICY])
    return None


async def housekeeping_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_HOUSEKEEPING_POLICY])
    return None


async def local_concierge_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_LOCAL_CONCIERGE_POLICY])
    return None


async def stay_monitor_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_STAY_MONITOR_POLICY])
    return None
