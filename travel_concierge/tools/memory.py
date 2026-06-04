# Copyright 2025 Google LLC
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

"""The 'memorize' tool for several agents to affect session states."""

import json
import os
from datetime import datetime
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions.state import State
from google.adk.tools import ToolContext

from travel_concierge.shared_libraries import constants

SAMPLE_SCENARIO_PATH = os.getenv(
    "HOTEL_CONCIERGE_SCENARIO",
    "travel_concierge/profiles/stay_empty_default.json",
)


def memorize_list(key: str, value: str, tool_context: ToolContext):
    """
    Memorize pieces of information.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be stored.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    if key not in mem_dict:
        mem_dict[key] = []
    if value not in mem_dict[key]:
        mem_dict[key].append(value)
    return {"status": f'Stored "{key}": "{value}"'}


def memorize(key: str, value: str, tool_context: ToolContext):
    """
    Memorize pieces of information, one key-value pair at a time.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be stored.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    mem_dict = tool_context.state
    mem_dict[key] = value
    return {"status": f'Stored "{key}": "{value}"'}


def forget(key: str, value: str, tool_context: ToolContext):
    """
    Forget pieces of information.

    Args:
        key: the label indexing the memory to store the value.
        value: the information to be removed.
        tool_context: The ADK tool context.

    Returns:
        A status message.
    """
    if tool_context.state.get(key) is None:
        tool_context.state[key] = []
    if value in tool_context.state[key]:
        tool_context.state[key].remove(value)
    return {"status": f'Removed "{key}": "{value}"'}


def _set_initial_states(source: dict[str, Any], target: State | dict[str, Any]):
    """Set initial session state from a JSON scenario file."""
    if constants.SYSTEM_TIME not in target:
        target[constants.SYSTEM_TIME] = str(datetime.now())

    if constants.STAY_INITIALIZED not in target:
        target[constants.STAY_INITIALIZED] = True
        target.update(source)

        stay = source.get(constants.STAY_KEY, {})
        if stay:
            target[constants.STAY_CHECK_IN] = stay.get("check_in_date", "")
            target[constants.STAY_CHECK_OUT] = stay.get("check_out_date", "")


def _load_precreated_stay(callback_context: CallbackContext):
    """Load the initial session state from the scenario JSON file.

    Set this as before_agent_callback on root_agent.
    """
    data = {}
    with open(SAMPLE_SCENARIO_PATH) as file:
        data = json.load(file)
        print(f"\nLoading Initial State: {data}\n")

    _set_initial_states(data["state"], callback_context.state)

# Example of using callbacks to ask user input
# this is incorerct for now since it is running at backend wiht stdin
# a prompt has added in the agent to confirm this form users

# def _before_process_payment(callback_context: CallbackContext):
#     """
#     ask user input before going to process payment
#     Args:
#         callback_context: The callback context.
#     """
#     callback_context.state["user_payment_confirmation"] = input(
#         "Please enter YES to confirm the payment, or NO to cancel: "
#     )

