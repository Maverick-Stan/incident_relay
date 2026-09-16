import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DATE_KEY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OFFSET_SUFFIX_PATTERN = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")
MINUTES_PER_HOUR = 60
WEEKEND_DAYS = (0, 6)
CORRECTION_PASSES = 3


def is_time_zone(value):
    if not isinstance(value, str):
        return False

    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return False

    return True


def parse_date_key(date_key):
    return date.fromisoformat(date_key)


def add_calendar_days(date_key, amount):
    if not DATE_KEY_PATTERN.match(date_key):
        raise TypeError("Invalid calendar date.")

    return (parse_date_key(date_key) + timedelta(days=amount)).isoformat()


def day_of_week(date_key):
    return parse_date_key(date_key).isoweekday() % 7


def is_weekend(date_key):
    return day_of_week(date_key) in WEEKEND_DAYS


def parse_instant(value):
    if isinstance(value, datetime):
        return to_utc(value)

    if not isinstance(value, str):
        return None

    text = value.strip()

    if DATE_KEY_PATTERN.match(text):
        return datetime.combine(parse_date_key(text), datetime.min.time())

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None and not OFFSET_SUFFIX_PATTERN.search(text):
        return parsed.astimezone().astimezone(timezone.utc).replace(tzinfo=None)

    return to_utc(parsed)


def as_instant(value):
    return parse_instant(value) if isinstance(value, str) else to_utc(value)


def to_utc(value):
    if value.tzinfo is None:
        return value

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def parts_at(value, time_zone):
    local = to_utc(value).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(time_zone))

    return {
        "year": local.year,
        "month": local.month,
        "day": local.day,
        "hour": local.hour,
        "minute": local.minute,
        "second": local.second,
    }


def local_date_key(value, time_zone):
    parts = parts_at(value, time_zone)

    return f"{parts['year']:04d}-{parts['month']:02d}-{parts['day']:02d}"


def zoned_date_time(date_key, minute_of_day, time_zone):
    requested = datetime.combine(parse_date_key(date_key), datetime.min.time()) + timedelta(minutes=minute_of_day)
    result = requested

    for _ in range(CORRECTION_PASSES):
        parts = parts_at(result, time_zone)
        actual = datetime(parts["year"], parts["month"], parts["day"], parts["hour"], parts["minute"], parts["second"])
        correction = requested - actual

        if not correction:
            break

        result = result + correction

    return result


def working_hours_status(start_at, end_at, working_hours, time_zone):
    start = parts_at(start_at, time_zone)
    end = parts_at(end_at, time_zone)
    start_date = f"{start['year']:04d}-{start['month']:02d}-{start['day']:02d}"
    end_date = f"{end['year']:04d}-{end['month']:02d}-{end['day']:02d}"
    start_minute = start["hour"] * MINUTES_PER_HOUR + start["minute"]
    end_minute = end["hour"] * MINUTES_PER_HOUR + end["minute"]
    working_day = not is_weekend(start_date)
    same_day = start_date == end_date

    return {
        "withinWorkingHours": same_day
        and working_day
        and start_minute >= working_hours["startMinute"]
        and end_minute <= working_hours["endMinute"],
        "localDate": start_date,
        "localStartMinute": start_minute,
        "localEndMinute": end_minute,
        "workingDay": working_day,
    }
