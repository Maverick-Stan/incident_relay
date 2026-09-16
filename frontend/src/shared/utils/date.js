// Every calendar date decision is made in the display zone, never the viewer's own,
// so the same demo data reads identically on every machine.
import {
    addCalendarDays,
    addCalendarMonths,
    dayOfWeek,
    displayZoneOffsetLabel,
    formatInZone,
    localDateKey,
    minutesOf,
    partsAt,
    zonedDateTime,
} from "./time-zone.js";

export { DISPLAY_TIME_ZONE, minutesOf, weekdayOf, zonedDateTime } from "./time-zone.js";

export function dateKey(value) {
    return localDateKey(value);
}

export function startOfDay(value) {
    return zonedDateTime(dateKey(value), 0);
}

export function addDays(value, amount) {
    return zonedDateTime(addCalendarDays(dateKey(value), amount), minutesOf(value));
}

export function startOfWeek(value) {
    const key = dateKey(value);
    return zonedDateTime(addCalendarDays(key, -dayOfWeek(key)), 0);
}

export function startOfMonth(value) {
    const { year, month } = partsAt(value);
    return zonedDateTime(`${year}-${String(month).padStart(2, "0")}-01`, 0);
}

export function addMonths(value, amount) {
    return zonedDateTime(addCalendarMonths(dateKey(value), amount), 0);
}

export function getViewRange(view, cursor) {
    if (view === "day") return [startOfDay(cursor), addDays(startOfDay(cursor), 1)];
    if (view === "month") return [startOfWeek(startOfMonth(cursor)), addDays(startOfWeek(startOfMonth(cursor)), 42)];
    return [startOfWeek(cursor), addDays(startOfWeek(cursor), 7)];
}

export function moveCursor(view, cursor, direction) {
    if (view === "day") return addDays(cursor, direction);
    if (view === "week") return addDays(cursor, direction * 7);
    if (view === "month") return addMonths(cursor, direction);
    return cursor;
}

export function formatHeading(view, cursor) {
    const options = { month: "long", year: "numeric" };
    if (view === "day") return formatInZone(cursor, { month: "long", day: "numeric", year: "numeric" });
    if (view === "week") {
        const start = startOfWeek(cursor);
        const end = addDays(start, 6);
        if (partsAt(start).month === partsAt(end).month) return formatInZone(cursor, options);
        return `${formatInZone(start, { month: "short" })} – ${formatInZone(end, { month: "short", year: "numeric" })}`;
    }
    return formatInZone(cursor, options);
}

export function formatTimeZoneOffset(value = new Date()) {
    return displayZoneOffsetLabel(value);
}

export function toDateInput(value) {
    return dateKey(value);
}

export function roundToNextHalfHour(value = new Date()) {
    const minutes = minutesOf(value);
    return zonedDateTime(dateKey(value), minutes + (30 - (minutes % 30)));
}

export function isSameDay(left, right) {
    return dateKey(left) === dateKey(right);
}

export function formatTime(value) {
    return formatInZone(value, { hour: "numeric", minute: "2-digit", hour12: true });
}

export function eventDefaults(cursor, requestedStart) {
    const now = new Date();
    const base = isSameDay(cursor, now) ? now : zonedDateTime(dateKey(cursor), 9 * 60);
    const start = requestedStart ? new Date(requestedStart) : roundToNextHalfHour(base);
    const end = new Date(start.getTime() + 60 * 60 * 1000);
    return { startAt: start, endAt: end, allDay: false };
}
