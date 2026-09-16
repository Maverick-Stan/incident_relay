import { useCallback, useEffect, useRef, useState } from "react";
import { incidentApi } from "../incidents/incident.api.js";
import { analyticsApi } from "../analytics/analytics.api.js";
import { serviceApi } from "../services/service.api.js";
import { eventApi } from "../events/event.api.js";
import { profileApi } from "../profiles/profile.api.js";
import "./command.css";

const SEVERITY_RANK = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };
const STATUS_LABELS = { TRIGGERED: "Triggered", ACKNOWLEDGED: "Acknowledged", RESOLVED: "Resolved" };
const DISPOSITION_LABELS = { CREATED_INCIDENT: "Created", GROUPED: "Grouped", SUPPRESSED_DUPLICATE: "Suppressed" };

const message = (error) => error.details?.fieldErrors
    ? Object.entries(error.details.fieldErrors).map(([field, errors]) => `${field}: ${errors.join(" ")}`).join(" ")
    : error.message;

function formatDuration(seconds) {
    if (seconds == null) return "—";
    const total = Math.round(seconds);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (hours) return `${hours}h ${minutes}m`;
    if (minutes) return `${minutes}m ${total % 60}s`;
    return `${total}s`;
}
function timeAgo(value) {
    const ms = Date.now() - new Date(value).getTime();
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ${mins % 60}m ago`;
    return `${Math.floor(hours / 24)}d ago`;
}

const SeverityChip = ({ value }) => <span className={`service-severity ${value.toLowerCase()}`}>{value}</span>;
const StatusChip = ({ value }) => <span className={`incident-status ${value.toLowerCase()}`}>{STATUS_LABELS[value] || value}</span>;
const canClaim = (incident) => !incident.assigneeId && incident.status !== "RESOLVED";
const canAcknowledge = (incident) => incident.status === "TRIGGERED";

// Safe direct actions: acknowledge only a triggered incident, claim only an unassigned one.
function IncidentActions({ incident, acting, onAct }) {
    if (!canAcknowledge(incident) && !canClaim(incident)) return null;
    const busy = acting === incident._id;
    return <div className="service-actions">
        {canAcknowledge(incident) && <button className="service-primary" disabled={busy} onClick={() => onAct(incident._id, incidentApi.acknowledge)}>{busy ? "Working…" : "Acknowledge"}</button>}
        {canClaim(incident) && <button disabled={busy} onClick={() => onAct(incident._id, incidentApi.claim)}>Claim</button>}
    </div>;
}

const initial = { status: "loading", data: null, error: "" };

export function CommandCenter({ onBusyChange = () => {} }) {
    const [inc, setInc] = useState(initial);
    const [ana, setAna] = useState(initial);
    const [svc, setSvc] = useState({ data: [] });
    const [ppl, setPpl] = useState({ data: [] });
    const [ev, setEv] = useState({ status: "loading", data: [], error: "", partial: false });
    const [acting, setActing] = useState("");
    const [actionError, setActionError] = useState("");
    const generation = useRef(0);

    const loadEvents = useCallback(async (services) => {
        setEv({ status: "loading", data: [], error: "", partial: false });
        const results = await Promise.allSettled(services.map((service) => eventApi.history(service._id).then((page) => ({ service, items: page.items }))));
        const items = results.filter((row) => row.status === "fulfilled").flatMap((row) => row.value.items.map((item) => ({ ...item, serviceName: row.value.service.name })));
        const partial = results.some((row) => row.status === "rejected");
        items.sort((a, b) => new Date(b.receivedAt) - new Date(a.receivedAt));
        if (items.length === 0 && partial) setEv({ status: "error", data: [], error: "Recent event activity could not be loaded.", partial });
        else setEv({ status: "ok", data: items.slice(0, 8), error: "", partial });
    }, []);

    const loadCore = useCallback(async () => {
        const ticket = ++generation.current;
        setInc(initial); setAna(initial);
        const [incidents, analytics, services, profiles] = await Promise.allSettled([incidentApi.list(), analyticsApi.get(), serviceApi.list(), profileApi.list()]);
        if (ticket !== generation.current) return;
        setInc(incidents.status === "fulfilled" ? { status: "ok", data: incidents.value, error: "" } : { status: "error", data: null, error: message(incidents.reason) });
        setAna(analytics.status === "fulfilled" ? { status: "ok", data: analytics.value, error: "" } : { status: "error", data: null, error: message(analytics.reason) });
        setPpl({ data: profiles.status === "fulfilled" ? profiles.value : [] });
        if (services.status === "fulfilled") { setSvc({ data: services.value }); loadEvents(services.value); }
        else { setSvc({ data: [] }); setEv({ status: "error", data: [], error: "Services unavailable, so recent events cannot be shown.", partial: false }); }
    }, [loadEvents]);

    useEffect(() => { loadCore(); return () => { generation.current++; }; }, [loadCore]);

    const refreshOperational = useCallback(async () => {
        const [incidents, analytics] = await Promise.allSettled([incidentApi.list(), analyticsApi.get()]);
        setInc(incidents.status === "fulfilled" ? { status: "ok", data: incidents.value, error: "" } : { status: "error", data: null, error: message(incidents.reason) });
        setAna(analytics.status === "fulfilled" ? { status: "ok", data: analytics.value, error: "" } : { status: "error", data: null, error: message(analytics.reason) });
    }, []);

    const act = async (id, action) => {
        setActing(id); setActionError(""); onBusyChange(true);
        try { await action(id); await refreshOperational(); }
        catch (failure) { setActionError(message(failure)); }
        finally { setActing(""); onBusyChange(false); }
    };

    const serviceName = (id) => svc.data.find((service) => service._id === id)?.name || "Unknown service";
    const personName = (id) => ppl.data.find((person) => person._id === id)?.name || "Unavailable responder";

    const incidents = inc.status === "ok" ? inc.data : [];
    const triggered = incidents.filter((incident) => incident.status === "TRIGGERED");
    const active = incidents.filter((incident) => incident.status !== "RESOLVED");
    const hero = [...triggered].sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] || new Date(a.createdAt) - new Date(b.createdAt))[0];
    const otherActive = active.filter((incident) => incident._id !== hero?._id)
        .sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] || new Date(a.createdAt) - new Date(b.createdAt));
    const busy = inc.status === "loading" || ana.status === "loading" || ev.status === "loading";

    const tiles = [
        { key: "unack", label: "Unacknowledged", value: inc.status === "ok" ? triggered.length : "—", tone: triggered.length ? "alert" : "" },
        { key: "active", label: "Active incidents", value: inc.status === "ok" ? active.length : "—" },
        { key: "mtta", label: "MTTA", value: ana.status === "ok" ? formatDuration(ana.data.acknowledgement.meanSeconds) : "—", sub: "Mean time to acknowledge" },
        { key: "mttr", label: "MTTR", value: ana.status === "ok" ? formatDuration(ana.data.resolution.meanSeconds) : "—", sub: "Mean time to resolve" },
        { key: "grouped", label: "Grouped events", value: ana.status === "ok" ? ana.data.events.grouped : "—" },
        { key: "suppressed", label: "Suppressed duplicates", value: ana.status === "ok" ? ana.data.events.suppressed : "—" },
    ];

    return <main className="services-main command-center">
        <div className="service-page-heading">
            <div><div className="service-eyebrow">WORKSPACE / COMMAND CENTER</div><h1>Command Center</h1><p>The live operational picture across every service.</p></div>
            <button disabled={busy} onClick={loadCore}>{busy ? "Refreshing…" : "Refresh"}</button>
        </div>

        {actionError && <div className="service-alert error" role="alert">{actionError}</div>}

        {/* Priority: the highest-severity unacknowledged incident dominates. */}
        {inc.status === "loading" ? <div className="service-panel service-empty" role="status">Loading operational status…</div>
            : inc.status === "error" ? <div className="service-alert error" role="alert">{inc.error} <button onClick={loadCore}>Retry</button></div>
                : hero ? <section className={`command-hero sev-${hero.severity.toLowerCase()}`} aria-label="Highest-priority unacknowledged incident">
                    <div className="command-hero-flag">Needs acknowledgment</div>
                    <div className="command-hero-body">
                        <div className="command-hero-chips"><SeverityChip value={hero.severity} /><StatusChip value={hero.status} /><span className="command-hero-ref">{hero.reference}</span></div>
                        <h2>{hero.title}</h2>
                        <p className="command-hero-meta">{serviceName(hero.serviceId)} · triggered {timeAgo(hero.createdAt)} · {hero.assigneeId ? `owned by ${personName(hero.assigneeId)}` : "unassigned"} · {hero.eventCount} event{hero.eventCount === 1 ? "" : "s"}</p>
                        <div className="command-hero-actions">
                            <IncidentActions incident={hero} acting={acting} onAct={act} />
                            <a className="command-hero-link" href={`#incidents/${hero._id}`}>View details →</a>
                        </div>
                    </div>
                </section> : <section className="command-hero clear" aria-label="No unacknowledged incidents">
                    <div className="command-hero-body"><h2>All clear</h2><p>No unacknowledged incidents right now. {active.length ? `${active.length} acknowledged incident${active.length === 1 ? "" : "s"} still in progress.` : "Nothing is currently active."}</p></div>
                </section>}

        {/* Compact operational summary. */}
        <section className="service-panel">
            <div className="service-section-heading"><h2>Operational summary</h2>{ana.status === "error" && <button onClick={refreshOperational}>Retry metrics</button>}</div>
            <div className="command-tiles">{tiles.map((tile) => <div className={`command-tile ${tile.tone || ""}`} key={tile.key}>
                <div className="command-tile-value">{tile.value}</div><div className="command-tile-label">{tile.label}</div>{tile.sub && <small>{tile.sub}</small>}
            </div>)}</div>
            {ana.status === "error" && <p className="service-muted">Response-time and triage metrics are temporarily unavailable.</p>}
        </section>

        <div className="command-columns">
            {/* Active incidents. */}
            <section className="service-panel">
                <div className="service-section-heading"><h2>Active incidents</h2><span>{inc.status === "ok" ? `${active.length} open` : ""}</span></div>
                {inc.status === "loading" ? <p role="status" className="service-muted">Loading…</p>
                    : inc.status === "error" ? <div className="service-alert error" role="alert">{inc.error} <button onClick={loadCore}>Retry</button></div>
                        : otherActive.length === 0 ? <p className="service-muted">{hero ? "No other active incidents." : "No active incidents."}</p>
                            : <ul className="command-list">{otherActive.map((incident) => <li key={incident._id} className="command-row">
                                <div className="command-row-main">
                                    <div className="command-row-head"><SeverityChip value={incident.severity} /><StatusChip value={incident.status} /><a href={`#incidents/${incident._id}`}>{incident.reference}</a></div>
                                    <strong>{incident.title}</strong>
                                    <small>{serviceName(incident.serviceId)} · {timeAgo(incident.createdAt)} · {incident.assigneeId ? personName(incident.assigneeId) : "Unassigned"}</small>
                                </div>
                                <IncidentActions incident={incident} acting={acting} onAct={act} />
                            </li>)}</ul>}
            </section>

            {/* Recent event activity. */}
            <section className="service-panel">
                <div className="service-section-heading"><h2>Recent event activity</h2>{ev.status === "ok" && ev.partial && <span className="command-partial">Partial</span>}</div>
                {ev.status === "loading" ? <p role="status" className="service-muted">Loading…</p>
                    : ev.status === "error" ? <div className="service-alert error" role="alert">{ev.error} <button onClick={() => (svc.data.length ? loadEvents(svc.data) : loadCore())}>Retry</button></div>
                        : ev.data.length === 0 ? <p className="service-muted">No events received yet.</p>
                            : <>
                                {ev.partial && <p className="service-muted">Some services could not be reached; showing the events that loaded.</p>}
                                <ul className="command-list">{ev.data.map((event) => <li key={event._id} className="command-row">
                                    <div className="command-row-main">
                                        <div className="command-row-head"><span className={`command-disposition ${event.disposition.toLowerCase()}`}>{DISPOSITION_LABELS[event.disposition]}</span><a href={event.incident.href}>{event.incident.reference}</a></div>
                                        <strong>{event.normalizedTitle}</strong>
                                        <small>{event.serviceName} · {event.normalizedSeverity} · {timeAgo(event.receivedAt)}</small>
                                    </div>
                                </li>)}</ul>
                            </>}
            </section>
        </div>
    </main>;
}
