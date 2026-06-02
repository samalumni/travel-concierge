"""Post-stay agent: feedback, preference extraction, billing, and checkout."""

from google.adk.agents import Agent

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import post_stay_policy_callback
from travel_concierge.sub_agents.post_stay import prompt
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.preferences import extract_preferences, update_guest_preferences
from travel_concierge.tools.room_charge import get_room_charges

post_stay_agent = Agent(
    model=MODEL,
    name="post_stay_agent",
    description="Post-stay concierge: collects feedback, extracts preferences, presents bill, confirms checkout.",
    instruction=prompt.POST_STAY_AGENT_INSTR,
    tools=[
        extract_preferences,
        update_guest_preferences,
        get_room_charges,
        memorize,
    ],
    before_model_callback=post_stay_policy_callback,
)
