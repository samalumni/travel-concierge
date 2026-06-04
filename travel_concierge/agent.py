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

"""IHG Hotel Concierge — root agent and app initialisation."""

import uuid

from google.adk.agents import Agent
from google.adk.apps import App
from openinference.instrumentation import using_session

from travel_concierge import prompt
from travel_concierge.hotel_policy.callbacks import root_agent_policy_callback
from travel_concierge.hotel_policy.plugin import HotelPolicyPlugin
from travel_concierge.sub_agents.in_stay.agent import in_stay_agent
from travel_concierge.sub_agents.post_stay.agent import post_stay_agent
from travel_concierge.sub_agents.pre_stay.agent import pre_stay_agent
from travel_concierge.tools.memory import _load_precreated_stay
from travel_concierge.tools.profile import load_guest_profile
from travel_concierge.tracing import instrument_adk_with_arize

from . import MODEL

_ = instrument_adk_with_arize()


with using_session(session_id=str(uuid.uuid4())):
    root_agent = Agent(
        model=MODEL,
        name="root_agent",
        description="IHG Hotel Concierge — guides guests through pre-arrival, in-stay, and post-stay.",
        instruction=prompt.ROOT_AGENT_INSTR,
        tools=[load_guest_profile],
        sub_agents=[
            pre_stay_agent,
            in_stay_agent,
            post_stay_agent,
        ],
        before_agent_callback=_load_precreated_stay,
        before_model_callback=root_agent_policy_callback,
    )

app = App(root_agent=root_agent, name="travel_concierge", plugins=[HotelPolicyPlugin()])
