"""Tools for stay_monitor_agent: activity booking checks and weather impact."""


def event_booking_check(event_name: str, event_date: str, event_location: str) -> dict:
    """Check the status of a booked local tour or activity.

    Args:
        event_name: Name of the tour or activity.
        event_date: Date of the event in YYYY-MM-DD format.
        event_location: Location or venue name.

    Returns:
        A dict with a "status" key describing the booking state.
    """
    print("Checking", event_name, event_date, event_location)
    return {"status": f"{event_name}: confirmed"}


def weather_impact_check(
    activity_name: str, activity_date: str, activity_location: str
) -> dict:
    """Check weather impact on an outdoor activity.

    Args:
        activity_name: Name of the outdoor activity.
        activity_date: Date of the activity in YYYY-MM-DD format.
        activity_location: Location of the activity.

    Returns:
        A dict with a "status" key describing any weather risk.
    """
    print("Checking weather for", activity_name, activity_date, activity_location)
    return {"status": f"{activity_name}: no weather disruption expected"}
