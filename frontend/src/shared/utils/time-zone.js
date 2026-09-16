// The calendar renders in one fixed zone rather than the viewer's own, so a demo
// seeded in UTC reads the same on every machine. Mirrors backend/src/shared/utils/time-zone.js.

export const DISPLAY_TIME_ZONE = "UTC";

const dateKeyPattern = /^\d{4}-\d{2}-\d{2}$/;
const pad = (value) => String(value).padStart(2, "0");

export function partsAt(value, timeZone = DISPLAY_TIME_ZONE) {
    const parts = new Intl.DateTimeFormat("en-CA", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
    }).formatToParts(new Date(value));
    return Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, Number(part.value)]));
}

export function localDateKey(value, timeZone = DISPLAY_TIME_ZONE) {
    const { year, month, day } = partsAt(value, timeZone);
    return `${year}-${pad(month)}-${pad(day)}`;
}

export function addCalendarDays(dateKey, amount) {
    if (!dateKeyPattern.test(dateKey)) throw new TypeError("Invalid calendar date.");
    const [year, month, day] = dateKey.split("-").map(Number);
    const value = new Date(Date.UTC(year, month - 1, day + amount));
    return `${value.getUTCFullYear()}-${pad(value.getUTCMonth() + 1)}-${pad(value.getUTCDate())}`;
}

export function addCalendarMonths(dateKey, amount) {
    const [year, month] = dateKey.split("-").map(Number);
    const value = new Date(Date.UTC(year, month - 1 + amount, 1));
    return `${value.getUTCFullYear()}-${pad(value.getUTCMonth() + 1)}-01`;
}

export function dayOfWeek(dateKey) {
    const [year, month, day] = dateKey.split("-").map(Number);
    return new Date(Date.UTC(year, month - 1, day)).getUTCDay();
}

// The instant that is `minuteOfDay` into `dateKey` in the display zone. The loop
// settles the offset, which matters for zones that observe daylight saving.
export function zonedDateTime(dateKey, minuteOfDay, timeZone = DISPLAY_TIME_ZONE) {
    const [year, month, day] = dateKey.split("-").map(Number);
    const requestedAsUtc = Date.UTC(year, month - 1, day, Math.floor(minuteOfDay / 60), minuteOfDay % 60);
    let result = new Date(requestedAsUtc);
    for (let iteration = 0; iteration < 3; iteration += 1) {
        const actual = partsAt(result, timeZone);
        const correction = requestedAsUtc - Date.UTC(actual.year, actual.month - 1, actual.day, actual.hour, actual.minute, actual.second);
        if (!correction) break;
        result = new Date(result.getTime() + correction);
    }
    return result;
}

export function minutesOf(value, timeZone = DISPLAY_TIME_ZONE) {
    const { hour, minute } = partsAt(value, timeZone);
    return hour * 60 + minute;
}

export function weekdayOf(value, timeZone = DISPLAY_TIME_ZONE) {
    return dayOfWeek(localDateKey(value, timeZone));
}

export function formatInZone(value, options, locale = "en-US") {
    return new Intl.DateTimeFormat(locale, { timeZone: DISPLAY_TIME_ZONE, ...options }).format(new Date(value));
}

// The display zone's own offset, so the grid gutter never advertises the viewer's clock.
export function displayZoneOffsetLabel(value = new Date()) {
    const { year, month, day, hour, minute, second } = partsAt(value);
    const offsetMinutes = Math.round((Date.UTC(year, month - 1, day, hour, minute, second) - new Date(value).setMilliseconds(0)) / 60000);
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const absolute = Math.abs(offsetMinutes);
    return `GMT${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`;
}
