"""Pre-stay agent: digital check-in and preference collection before arrival."""

from google.adk.agents import Agent

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import pre_stay_policy_callback
from travel_concierge.sub_agents.pre_stay import prompt
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.preferences import update_guest_preferences

pre_stay_agent = Agent(
    model=MODEL,
    name="pre_stay_agent",
    description="Collects digital check-in information and room preferences before the guest arrives.",
    instruction=prompt.PRE_STAY_AGENT_INSTR,
    tools=[memorize, update_guest_preferences],
    before_model_callback=pre_stay_policy_callback,
)
