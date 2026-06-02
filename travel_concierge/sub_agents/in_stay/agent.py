"""In-stay agent: orchestrates dining, housekeeping, local concierge, and monitoring."""

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import (
    dining_policy_callback,
    housekeeping_policy_callback,
    in_stay_policy_callback,
    local_concierge_policy_callback,
    stay_monitor_policy_callback,
)
from travel_concierge.sub_agents.in_stay import prompt
from travel_concierge.sub_agents.in_stay.tools import event_booking_check, weather_impact_check
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.places import get_places_toolset
from travel_concierge.tools.room_charge import get_room_charges, post_room_charge
from travel_concierge.tools.search import google_search_grounding

try:
    _places_toolset = get_places_toolset()
    _maps_tools = [_places_toolset]
except EnvironmentError:
    _maps_tools = []

dining_agent = Agent(
    model=MODEL,
    name="dining_agent",
    description="Hotel dining concierge: restaurant reservations and room service orders.",
    instruction=prompt.DINING_AGENT_INSTR,
    tools=[post_room_charge, memorize],
    before_model_callback=dining_policy_callback,
)

housekeeping_agent = Agent(
    model=MODEL,
    name="housekeeping_agent",
    description="Hotel housekeeping concierge: room requests, amenities, and maintenance.",
    instruction=prompt.HOUSEKEEPING_AGENT_INSTR,
    tools=[post_room_charge, memorize],
    before_model_callback=housekeeping_policy_callback,
)

local_concierge_agent = Agent(
    model=MODEL,
    name="local_concierge_agent",
    description="Local area concierge: transport options and local restaurant/attraction recommendations.",
    instruction=prompt.LOCAL_CONCIERGE_AGENT_INSTR,
    tools=[google_search_grounding, post_room_charge, memorize, *_maps_tools],
    before_model_callback=local_concierge_policy_callback,
)

stay_monitor_agent = Agent(
    model=MODEL,
    name="stay_monitor_agent",
    description="Monitors local activity bookings and weather impact for the guest's stay.",
    instruction=prompt.STAY_MONITOR_INSTR,
    tools=[event_booking_check, weather_impact_check],
    output_key="stay_monitor_summary",
    before_model_callback=stay_monitor_policy_callback,
)

in_stay_agent = Agent(
    model=MODEL,
    name="in_stay_agent",
    description="In-stay hotel concierge: routes guest requests during their active stay.",
    instruction=prompt.IN_STAY_AGENT_INSTR,
    sub_agents=[stay_monitor_agent],
    tools=[
        AgentTool(agent=dining_agent),
        AgentTool(agent=housekeeping_agent),
        AgentTool(agent=local_concierge_agent),
        get_room_charges,
        memorize,
    ],
    before_model_callback=in_stay_policy_callback,
)
