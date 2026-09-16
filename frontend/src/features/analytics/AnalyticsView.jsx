import { useEffect, useRef, useState } from "react";
import { analyticsApi } from "./analytics.api.js";
import "./analytics.css";

const WINDOWS = [
    { id: "all", label: "All time" },
    { id: "30d", label: "Last 30 days", days: 30 },
    { id: "90d", label: "Last 90 days", days: 90 },
];

const message = (error) => error.details?.fieldErrors
    ? Object.entries(error.details.fieldErrors).map(([field, errors]) => `${field}: ${errors.join(" ")}`).join(" ")
    : error.message;

function formatDuration(seconds) {
    if (seconds == null) return "—";
    const total = Math.round(seconds);
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hours) return `${hours}h ${minutes}m`;
    if (minutes) return `${minutes}m ${secs}s`;
    return `${secs}s`;
}

function MetricCard({ abbr, name, helper, meanSeconds, sampleSize }) {
    return <div className="analytics-metric">
        <div className="analytics-metric-abbr">{abbr}</div>
        <div className="analytics-metric-value">{formatDuration(meanSeconds)}</div>
        <div className="analytics-metric-name">{name}</div>
        <p className="analytics-metric-helper">{helper}</p>
        <div className="analytics-metric-sample">{sampleSize === 0 ? "No incidents in range" : `n = ${sampleSize} incident${sampleSize === 1 ? "" : "s"}`}</div>
    </div>;
}

function BarList({ rows, emptyLabel }) {
    if (!rows.length || rows.every((row) => row.count === 0)) return <p className="service-muted">{emptyLabel}</p>;
    const max = Math.max(1, ...rows.map((row) => row.count));
    return <ul className="analytics-bars">{rows.map((row) => <li key={row.key}>
        <div className="analytics-bar-head"><span>{row.label}</span><span className="analytics-bar-count">{row.count}</span></div>
        <div className="analytics-bar-track"><div className={`analytics-bar-fill ${row.tone || ""}`} style={{ width: `${(row.count / max) * 100}%` }} /></div>
    </li>)}</ul>;
}

export function AnalyticsView() {
    const [windowId, setWindowId] = useState("all");
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const generation = useRef(0);

    const load = async (id) => {
        const ticket = ++generation.current; setLoading(true); setError("");
        const chosen = WINDOWS.find((option) => option.id === id);
        const params = chosen?.days ? { since: new Date(Date.now() - chosen.days * 86400000).toISOString(), until: new Date().toISOString() } : {};
        try { const result = await analyticsApi.get(params); if (ticket === generation.current) setData(result); }
        catch (failure) { if (ticket === generation.current) setError(message(failure)); }
        finally { if (ticket === generation.current) setLoading(false); }
    };
    useEffect(() => { load(windowId); return () => { generation.current++; }; }, [windowId]);

    const eventTiles = data && [
        { key: "grouped", label: "Grouped events", value: data.events.grouped, helper: "Events merged into an existing incident" },
        { key: "suppressed", label: "Suppressed duplicates", value: data.events.suppressed, helper: "Exact duplicates that were dropped" },
        { key: "created", label: "Created incidents", value: data.events.created, helper: "Events that opened a new incident" },
        { key: "total", label: "Total events", value: data.events.total, helper: "All events received in range" },
    ];

    return <main className="services-main">
        <div className="service-eyebrow">WORKSPACE / ANALYTICS</div>
        <div className="service-page-heading">
            <div><h1>Post-incident analytics</h1><p>Computed live from stored incident and event facts — no separate rollups.</p></div>
            <label className="incident-filter">Date window<select value={windowId} disabled={loading} onChange={(event) => setWindowId(event.target.value)}>{WINDOWS.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        </div>

        {error && <div className="service-alert error" role="alert">{error} <button onClick={() => load(windowId)}>Retry</button></div>}
        {loading ? <div className="service-panel service-empty" role="status">Loading analytics…</div> : data && <>
            <section className="service-panel">
                <div className="service-section-heading"><h2>Response times</h2><span>{data.totals.incidents} incidents in range</span></div>
                <div className="analytics-metric-grid">
                    <MetricCard abbr="MTTA" name="Mean time to acknowledge" helper="Arithmetic mean of the elapsed time from incident creation to acknowledgment." meanSeconds={data.acknowledgement.meanSeconds} sampleSize={data.acknowledgement.sampleSize} />
                    <MetricCard abbr="MTTR" name="Mean time to resolve" helper="Arithmetic mean from creation to resolution. Unresolved incidents are excluded from this figure." meanSeconds={data.resolution.meanSeconds} sampleSize={data.resolution.sampleSize} />
                </div>
            </section>

            <section className="service-panel">
                <div className="service-section-heading"><h2>Event triage</h2><span>Grouped and suppressed counts</span></div>
                <div className="analytics-tiles">{eventTiles.map((tile) => <div className="analytics-tile" key={tile.key}><div className="analytics-tile-value">{tile.value}</div><div className="analytics-tile-label">{tile.label}</div><small>{tile.helper}</small></div>)}</div>
            </section>

            <section className="service-panel">
                <div className="service-section-heading"><h2>Incident volume</h2><span>By service, severity, and responder</span></div>
                <div className="analytics-volume">
                    <div><h3>By service</h3><BarList emptyLabel="No incidents in range." rows={data.volumeByService.map((row) => ({ key: row.serviceId, label: row.name, count: row.count }))} /></div>
                    <div><h3>By severity</h3><BarList emptyLabel="No incidents in range." rows={data.volumeBySeverity.map((row) => ({ key: row.severity, label: row.severity, count: row.count, tone: row.severity.toLowerCase() }))} /></div>
                    <div><h3>By responder</h3><p className="service-muted analytics-note">Responder = the incident's current assignee. Unowned incidents appear as “Unassigned.”</p><BarList emptyLabel="No incidents in range." rows={data.volumeByResponder.map((row) => ({ key: row.responderId || "unassigned", label: row.name, count: row.count }))} /></div>
                </div>
            </section>

            <p className="service-muted analytics-rule"><strong>Date-window rule:</strong> {data.window.rule}</p>
        </>}
    </main>;
}
