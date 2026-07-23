from datetime import date, timedelta
from homeassistant.util import dt as dt_util

def get_last_sunday() -> date:
    """Returns the datetime.date object corresponding to the last sunday before today.
    Excludes the present day (if it is a sunday).
    """
    today = dt_util.now().date()
    days_since_sunday = today.weekday() + 1  # weekday() -> Monday=0, Sunday=6
    previous_sunday = today - timedelta(days=days_since_sunday)
    return previous_sunday


def months_ago(today: date, months: int) -> date:
    """Return the date `months` ago from `today`."""
    month = today.month - months
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    # calendar is not imported, let's just do an inline import or we'll add it to the top
    import calendar
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)

def six_months_ago(today: date) -> date:
    """Return the date 6 months ago from `today`."""
    return months_ago(today, 6)

def eight_months_ago(today: date) -> date:
    """Return the date 8 months ago from `today`."""
    return months_ago(today, 8)
