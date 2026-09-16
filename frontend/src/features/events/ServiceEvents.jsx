import { useEffect, useRef, useState } from "react";
import { Modal } from "../../shared/components/Modal.jsx";
import { eventApi } from "./event.api.js";
import "./events.css";

const newId = () => `test-${crypto.randomUUID()}`;
const errorText = (error) => error.details?.fieldErrors ? Object.entries(error.details.fieldErrors).map(([field, messages]) => `${field}: ${messages.join(" ")}`).join(" ") : error.message;
const incidentHash = () => /^#incidents\/([a-f\d]{24})$/i.exec(window.location.hash)?.[1] || "";
const STATUS_LABELS = { TRIGGERED: "Triggered", ACKNOWLEDGED: "Acknowledged", RESOLVED: "Resolved" };
const DISPOSITION_SHORT = { CREATED_INCIDENT: "Created", GROUPED: "Grouped", SUPPRESSED_DUPLICATE: "Suppressed" };
const DISPOSITION_LABELS = { CREATED_INCIDENT: "Created incident", GROUPED: "Grouped", SUPPRESSED_DUPLICATE: "Suppressed duplicate" };

export function IncidentLinkPreview() {
    const [id, setId] = useState(incidentHash);
    const [record, setRecord] = useState(null);
    const [error, setError] = useState("");
    const [version, setVersion] = useState(0);
    useEffect(() => { const change = () => setId(incidentHash()); window.addEventListener("hashchange", change); return () => window.removeEventListener("hashchange", change); }, []);
    useEffect(() => {
        let current = true; setRecord(null); setError("");
        if (id) eventApi.incident(id).then((value) => { if (current) setRecord(value); }).catch((failure) => { if (current) setError(errorText(failure)); });
        return () => { current = false; };
    }, [id, version]);
    if (!id) return null;
    const close = () => { window.location.hash = ""; };
    return <Modal className="relay-event-modal" label="Incident preview" onClose={close}>
        <div className="service-section-heading"><h2>{record?.reference || "Incident"}</h2><button onClick={close} data-autofocus>Close</button></div>
        {error ? <div role="alert" className="service-alert error">{error} <button onClick={() => setVersion(version + 1)}>Retry</button></div> : !record ? <p role="status">Loading incident…</p> : <>
            <h3>{record.title}</h3><p><strong>{STATUS_LABELS[record.status] || record.status}</strong> · {record.severity} · {record.eventCount} events</p><p>Created {new Date(record.createdAt).toLocaleString()}</p>
            <h3>Response workflow snapshot</h3><ol className="service-workflow">{record.workflowRun.map((step) => <li key={step.order}><strong>{step.title}</strong><p>{step.instructions}</p><small>{step.completed ? "Completed" : "Open"} · {step.required ? "Required" : "Optional"}</small></li>)}</ol>{!record.workflowRun.length && <p>No workflow steps.</p>}
            <h3>Timeline</h3><ol className="service-workflow">{record.timeline.map((entry, index) => <li key={index}><small>{new Date(entry.at).toLocaleString()}</small><p>{entry.message}</p></li>)}</ol>
        </>}
    </Modal>;
}

function SendTestEvent({ service, onClose, onSent }) {
    const [key, setKey] = useState("");
    const [form, setForm] = useState(() => ({ source: "test-simulator", sourceEventId: newId(), title: "Database latency elevated", severity: service.defaultSeverity, component: "database", alertType: "latency", payload: '{"latencyMs": 1200}' }));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [result, setResult] = useState(null);
    const lastDelivery = useRef(null);
    const set = (field, value) => { setForm((current) => ({ ...current, [field]: value })); setResult(null); };
    const send = async (retry = false) => {
        setError(""); setResult(null);
        try {
            const body = retry ? lastDelivery.current : { source: form.source, sourceEventId: form.sourceEventId, title: form.title, severity: form.severity, labels: { component: form.component, alertType: form.alertType }, payload: JSON.parse(form.payload) };
            if (!body) return;
            setBusy(true); lastDelivery.current = body;
            const response = await eventApi.send(service._id, key.trim(), body);
            setResult(response); onSent();
        } catch (failure) { setError(failure instanceof SyntaxError ? "Payload must be valid JSON." : errorText(failure)); }
        finally { setBusy(false); }
    };
    return <Modal className="relay-event-modal" label="Send Test Event" onClose={() => { if (!busy) onClose(); }}>
        <div className="service-section-heading"><div><h2>Send Test Event</h2><p>{service.name}</p></div><button disabled={busy} onClick={onClose}>Close</button></div>
        <p>This sends a real event. Use a new delivery ID to evaluate triage; retrying an existing ID returns its original outcome.</p>
        {error && <div className="service-alert error" role="alert">{error}</div>}
        <form onSubmit={(event) => { event.preventDefault(); send(); }} className="service-form"><fieldset disabled={busy}><div className="service-form-grid">
            <label className="service-span">Integration key<input data-autofocus type="password" required autoComplete="off" maxLength={256} value={key} onChange={(e) => setKey(e.target.value)} /><small>Paste the saved key for this service. It stays in this dialog only.</small></label>
            <label>Source<input required maxLength={120} value={form.source} onChange={(e) => set("source", e.target.value)} /></label>
            <label>Source event ID<input required maxLength={200} value={form.sourceEventId} onChange={(e) => set("sourceEventId", e.target.value)} /></label>
            <label className="service-span">Event title<input required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} /></label>
            <label>Severity<select value={form.severity} onChange={(e) => set("severity", e.target.value)}>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Component<input required maxLength={200} value={form.component} onChange={(e) => set("component", e.target.value)} /></label>
            <label>Alert type<input required maxLength={200} value={form.alertType} onChange={(e) => set("alertType", e.target.value)} /></label>
            <label className="service-span">Payload (JSON)<textarea rows={3} required value={form.payload} onChange={(e) => set("payload", e.target.value)} /></label>
        </div><div className="service-form-footer"><button type="button" onClick={() => set("sourceEventId", newId())}>New delivery ID</button><button className="service-primary" type="submit">{busy ? "Sending…" : "Send event"}</button></div></fieldset></form>
        {lastDelivery.current && <button disabled={busy || !key.trim()} onClick={() => send(true)}>Retry last delivery unchanged</button>}
        {result && <section className="service-key-panel event-result" role="status"><h3>{result.idempotentReplay ? "Idempotent retry — original outcome" : "New event received"}</h3><p><strong>{DISPOSITION_LABELS[result.event.disposition] || result.event.disposition}</strong></p><p>{result.event.reason}</p>{result.idempotentReplay && <p>No event, incident, or timeline entry was added. This retry is not a new suppressed duplicate.</p>}<a href={result.event.incident.href} onClick={onClose}>View {result.event.incident.reference} →</a></section>}
        <p className="service-muted">For an exact duplicate, keep the content and use a new delivery ID. For grouping, change the payload while keeping the component and alert type. For a new incident, use a different component or alert type.</p>
    </Modal>;
}

export function ServiceEvents({ service, disabled = false }) {
    const [events, setEvents] = useState([]);
    const [total, setTotal] = useState(0);
    const [nextOffset, setNextOffset] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [sending, setSending] = useState(false);
    const generation = useRef(0);
    const load = async (offset = 0) => {
        const ticket = ++generation.current; setLoading(true); setError("");
        try { const data = await eventApi.history(service._id, offset); if (ticket === generation.current) { setEvents((current) => offset ? [...current, ...data.items] : data.items); setTotal(data.total); setNextOffset(data.nextOffset); } }
        catch (failure) { if (ticket === generation.current) setError(errorText(failure)); }
        finally { if (ticket === generation.current) setLoading(false); }
    };
    useEffect(() => { load(); return () => { generation.current++; }; }, [service._id]);
    return <section className="service-panel">
        <div className="service-section-heading"><div><h2>Event history</h2><p>{total} recorded events · retries do not add records</p></div><button className="service-primary" disabled={disabled} onClick={() => setSending(true)}>Send Test Event</button></div>
        {error && <div role="alert" className="service-alert error">{error} <button onClick={() => load()}>Retry history</button></div>}{loading && <p role="status">Loading events…</p>}
        {!loading && !error && events.length === 0 && <p>No events yet. Send a test event to see its triage decision here.</p>}
        <div className="event-history">{events.map((event) => <article key={event._id} className="event-record"><div className="service-section-heading"><h3>{event.normalizedTitle}</h3><span>{event.normalizedSeverity}</span></div><p><strong className="event-disposition">{DISPOSITION_SHORT[event.disposition] || event.disposition}</strong> · <a href={event.incident.href}>{event.incident.reference}</a></p><p>{event.reason}</p><small>{new Date(event.receivedAt).toLocaleString()} · {event.source} · {event.sourceEventId}</small><details><summary>Event payload and decision</summary><pre>{JSON.stringify({ rawPayload: event.rawPayload, triageDecision: event.triageDecision, duplicateOfEventId: event.duplicateOfEventId }, null, 2)}</pre></details></article>)}</div>
        <div className="service-actions"><button disabled={loading} onClick={() => load()}>Refresh history</button>{nextOffset !== null && <button disabled={loading} onClick={() => load(nextOffset)}>Load more events</button>}</div>
        {sending && <SendTestEvent service={service} onClose={() => setSending(false)} onSent={() => load()} />}
    </section>;
}
