import { useEffect, useRef, useState } from "react";
import { Modal } from "../../shared/components/Modal.jsx";
import { serviceApi } from "../services/service.api.js";
import { profileApi } from "../profiles/profile.api.js";
import { incidentApi } from "./incident.api.js";
import "./incidents.css";

const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const STATUS_LABELS = { TRIGGERED: "Triggered", ACKNOWLEDGED: "Acknowledged", RESOLVED: "Resolved" };
const STATUS_FILTERS = ["ALL", "TRIGGERED", "ACKNOWLEDGED", "RESOLVED"];

const message = (error) => {
    const fields = error.details?.fieldErrors;
    return fields ? Object.entries(fields).map(([field, errors]) => `${field}: ${errors.join(" ")}`).join(" ") : error.message;
};
const when = (value) => (value ? new Date(value).toLocaleString() : "—");
const SeverityChip = ({ value }) => <span className={`service-severity ${value.toLowerCase()}`}>{value}</span>;
const StatusChip = ({ value }) => <span className={`incident-status ${value.toLowerCase()}`}>{STATUS_LABELS[value] || value}</span>;

function IncidentForm({ services, owners, defaultServiceId, onCreate, onCancel, onBusyChange }) {
    const initialService = services.find((service) => service._id === defaultServiceId) || services[0];
    const [form, setForm] = useState({
        serviceId: initialService?._id || "", title: "", description: "",
        severity: initialService?.defaultSeverity || "HIGH", assigneeId: "",
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const errorRef = useRef(null);
    const set = (field, value) => setForm((current) => ({ ...current, [field]: value }));
    const pickService = (id) => setForm((current) => ({ ...current, serviceId: id, severity: services.find((service) => service._id === id)?.defaultSeverity || current.severity }));
    const submit = async (event) => {
        event.preventDefault(); setSaving(true); onBusyChange(true); setError("");
        try {
            await onCreate({
                serviceId: form.serviceId, title: form.title.trim(), description: form.description.trim(),
                severity: form.severity, ...(form.assigneeId ? { assigneeId: form.assigneeId } : {}),
            });
        } catch (failure) { setError(message(failure)); setTimeout(() => errorRef.current?.focus(), 0); }
        finally { setSaving(false); onBusyChange(false); }
    };
    if (services.length === 0) {
        return <div className="service-panel service-empty"><h2>No services available</h2><p>Create a service first so incidents have an owner and a response workflow.</p><button onClick={onCancel}>← Back to incidents</button></div>;
    }
    return <div className="service-panel"><form className="service-form" onSubmit={submit}>
        {error && <div className="service-alert error" role="alert" tabIndex={-1} ref={errorRef}>{error}</div>}
        <fieldset disabled={saving}>
            <div className="service-form-grid">
                <label>Service<select required value={form.serviceId} onChange={(e) => pickService(e.target.value)}><option value="">Choose a service</option>{services.map((service) => <option key={service._id} value={service._id}>{service.name}</option>)}</select></label>
                <label>Severity<select value={form.severity} onChange={(e) => set("severity", e.target.value)}>{SEVERITIES.map((severity) => <option key={severity}>{severity}</option>)}</select></label>
                <label className="service-span">Title<input autoFocus required maxLength={200} value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Checkout latency elevated" /></label>
                <label className="service-span">Description<textarea maxLength={4000} rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What is happening? Optional." /></label>
                <label>Assignee<select value={form.assigneeId} onChange={(e) => set("assigneeId", e.target.value)}><option value="">Unassigned</option>{owners.map((owner) => <option key={owner._id} value={owner._id}>{owner.name}</option>)}</select><small>You can also claim or assign the incident later.</small></label>
            </div>
            <div className="service-form-footer"><button type="button" onClick={onCancel}>Cancel</button><button className="service-primary" type="submit">{saving ? "Creating…" : "Create incident"}</button></div>
        </fieldset>
    </form></div>;
}

function EscalateDialog({ incident, owners, personName, onClose, onEscalate }) {
    const options = SEVERITIES.slice(SEVERITIES.indexOf(incident.severity) + 1);
    const [form, setForm] = useState({ severity: options[0] || "", reason: "", assigneeId: "" });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const set = (field, value) => setForm((current) => ({ ...current, [field]: value }));
    const submit = async (event) => {
        event.preventDefault(); setBusy(true); setError("");
        try {
            await onEscalate({ severity: form.severity, reason: form.reason.trim(), ...(form.assigneeId ? { assigneeId: form.assigneeId } : {}) });
            onClose();
        } catch (failure) { setError(message(failure)); setBusy(false); }
    };
    return <Modal className="relay-event-modal" label="Escalate incident" onClose={() => { if (!busy) onClose(); }}>
        <div className="service-section-heading"><div><h2>Escalate {incident.reference}</h2><p>Raise severity above <strong>{incident.severity}</strong>. A reason is required.</p></div><button disabled={busy} onClick={onClose}>Close</button></div>
        {error && <div className="service-alert error" role="alert">{error}</div>}
        <form className="service-form" onSubmit={submit}><fieldset disabled={busy}><div className="service-form-grid">
            <label>New severity<select required value={form.severity} onChange={(e) => set("severity", e.target.value)}>{options.map((severity) => <option key={severity}>{severity}</option>)}</select></label>
            <label>Reassign to<select value={form.assigneeId} onChange={(e) => set("assigneeId", e.target.value)}><option value="">Keep {incident.assigneeId ? personName(incident.assigneeId) : "unassigned"}</option>{owners.map((owner) => <option key={owner._id} value={owner._id}>{owner.name}</option>)}</select></label>
            <label className="service-span">Reason<textarea required rows={3} maxLength={2000} value={form.reason} onChange={(e) => set("reason", e.target.value)} data-autofocus placeholder="Why is this being escalated?" /></label>
        </div><div className="service-form-footer"><button type="button" onClick={onClose}>Cancel</button><button className="service-primary" type="submit">{busy ? "Escalating…" : "Escalate"}</button></div></fieldset></form>
    </Modal>;
}

function IncidentDetail({ incident, owners, serviceName, personName, onChange, onBusyChange }) {
    const [acting, setActing] = useState(false);
    const [error, setError] = useState("");
    const [assignee, setAssignee] = useState(incident.assigneeId || "");
    const [note, setNote] = useState("");
    const [resolution, setResolution] = useState("");
    const [escalating, setEscalating] = useState(false);
    useEffect(() => { setAssignee(incident.assigneeId || ""); }, [incident.assigneeId]);
    const resolved = incident.status === "RESOLVED";
    const run = async (action, after) => {
        setError(""); setActing(true); onBusyChange(true);
        try { onChange(await action()); after?.(); return true; }
        catch (failure) { setError(message(failure)); return false; }
        finally { setActing(false); onBusyChange(false); }
    };
    const canResolve = incident.status === "ACKNOWLEDGED" && incident.openRequiredSteps === 0 && resolution.trim().length > 0;
    return <>
        <div className="incident-detail-head">
            <div><div className="incident-detail-title"><h2>{incident.title}</h2><StatusChip value={incident.status} /><SeverityChip value={incident.severity} /></div>
                <p className="service-muted">{incident.reference} · {serviceName(incident.serviceId)} · opened {when(incident.createdAt)}</p></div>
        </div>
        {resolved && <div className="service-alert success" role="status">This incident is resolved and read-only. Its history is preserved below.</div>}
        {error && <div className="service-alert error" role="alert">{error}</div>}

        <section className="service-panel">
            <div className="service-section-heading"><h3>Overview</h3><span>Origin: {incident.origin === "EVENT" ? "Event intake" : "Manual"}</span></div>
            <p className="service-description">{incident.description || "No description provided."}</p>
            <dl className="service-facts">
                <div><dt>Assignee</dt><dd>{incident.assigneeId ? personName(incident.assigneeId) : "Unassigned"}</dd></div>
                <div><dt>Acknowledged</dt><dd>{incident.acknowledgedBy ? `${personName(incident.acknowledgedBy)}` : "Not yet"}<br /><small>{when(incident.acknowledgedAt)}</small></dd></div>
                <div><dt>Events</dt><dd>{incident.eventCount}</dd></div>
                <div><dt>Resolved</dt><dd>{incident.resolvedBy ? personName(incident.resolvedBy) : "No"}<br /><small>{when(incident.resolvedAt)}</small></dd></div>
            </dl>
            {resolved && incident.resolutionNote && <div className="incident-resolution"><dt>Resolution note</dt><p className="service-description">{incident.resolutionNote}</p></div>}
        </section>

        {!resolved && <section className="service-panel">
            <div className="service-section-heading"><h3>Respond</h3><span>Ownership is independent from status.</span></div>
            <div className="incident-action-grid">
                <div className="incident-action">
                    <h4>Acknowledge</h4><p className="service-muted">Move TRIGGERED → ACKNOWLEDGED.</p>
                    <button className="service-primary" disabled={acting || incident.status !== "TRIGGERED"} onClick={() => run(() => incidentApi.acknowledge(incident._id))}>Acknowledge</button>
                    {incident.status !== "TRIGGERED" && <small>Already acknowledged.</small>}
                </div>
                <div className="incident-action">
                    <h4>Ownership</h4>
                    <label className="incident-assign">Assignee<select disabled={acting} value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="">Unassigned</option>{owners.map((owner) => <option key={owner._id} value={owner._id}>{owner.name}</option>)}</select></label>
                    <div className="service-actions">
                        <button disabled={acting || (assignee || "") === (incident.assigneeId || "")} onClick={() => run(() => incidentApi.assign(incident._id, assignee || null))}>Save assignee</button>
                        <button disabled={acting || Boolean(incident.assigneeId)} onClick={() => run(() => incidentApi.claim(incident._id))}>Claim</button>
                    </div>
                    {incident.assigneeId && <small>Claim is available only when unassigned.</small>}
                </div>
                <div className="incident-action">
                    <h4>Escalate</h4><p className="service-muted">Raise severity and optionally reassign, with a reason.</p>
                    <button disabled={acting || incident.severity === "CRITICAL"} onClick={() => setEscalating(true)}>Escalate</button>
                    {incident.severity === "CRITICAL" && <small>Already at the highest severity.</small>}
                </div>
            </div>
            <div className="incident-note-box">
                <label>Add a note<textarea rows={2} maxLength={4000} value={note} disabled={acting} onChange={(e) => setNote(e.target.value)} placeholder="Share an update for the timeline." /></label>
                <button disabled={acting || note.trim().length === 0} onClick={() => run(() => incidentApi.addNote(incident._id, note.trim()), () => setNote(""))}>Add note</button>
            </div>
        </section>}

        <section className="service-panel">
            <div className="service-section-heading"><h3>Response workflow</h3><span>{incident.openRequiredSteps} required step{incident.openRequiredSteps === 1 ? "" : "s"} open</span></div>
            {incident.workflowRun.length === 0 ? <p className="service-muted">No workflow steps for this incident.</p> : <>
                <p className="service-muted">Copied from the service template when this incident opened, so later template edits never change it. Steps run top to bottom — a step unlocks once the ones above it are complete.</p>
                <ol className="service-workflow">{incident.workflowRun.map((stepItem, index) => {
                    const earlierOpen = incident.workflowRun.slice(0, index).some((prev) => !prev.completed);
                    const laterDone = incident.workflowRun.slice(index + 1).some((next) => next.completed);
                    return <li key={stepItem.order}><div><strong>{stepItem.title}</strong><span>{stepItem.required ? "Required" : "Optional"} · {stepItem.completed ? "Completed" : "Open"}</span></div><p>{stepItem.instructions}</p>
                        {stepItem.completed && <small className="incident-step-meta">Completed by {personName(stepItem.completedBy)} · {when(stepItem.completedAt)}</small>}
                        {!resolved ? <div className="service-actions">{stepItem.completed
                            ? <button disabled={acting || laterDone} onClick={() => run(() => incidentApi.step(incident._id, stepItem.order, false))}>Undo completion</button>
                            : <button disabled={acting || earlierOpen} onClick={() => run(() => incidentApi.step(incident._id, stepItem.order, true))}>Mark complete</button>}
                            {stepItem.completed && laterDone && <small className="service-muted">Undo later steps first.</small>}
                            {!stepItem.completed && earlierOpen && <small className="service-muted">Complete the steps above first.</small>}</div>
                            : <small className="service-muted">{stepItem.completed ? "Completed" : "Not completed"}</small>}
                    </li>;
                })}</ol></>}
        </section>

        {!resolved && <section className="service-panel">
            <div className="service-section-heading"><h3>Resolve</h3><span>Requires acknowledgment, required steps, and a note.</span></div>
            <label>Resolution note<textarea rows={3} maxLength={4000} value={resolution} disabled={acting} onChange={(e) => setResolution(e.target.value)} placeholder="Describe how the incident was resolved." /></label>
            {incident.status !== "ACKNOWLEDGED" && <small className="service-muted">Acknowledge the incident before resolving.</small>}
            {incident.status === "ACKNOWLEDGED" && incident.openRequiredSteps > 0 && <small className="service-muted">Complete the {incident.openRequiredSteps} open required step(s) first.</small>}
            <div className="service-form-footer"><button className="service-primary" disabled={acting || !canResolve} onClick={() => run(() => incidentApi.resolve(incident._id, resolution.trim()))}>Resolve incident</button></div>
        </section>}

        {incident.notes.length > 0 && <section className="service-panel">
            <div className="service-section-heading"><h3>Notes</h3><span>{incident.notes.length}</span></div>
            {incident.notes.map((entry, index) => <div className="incident-note" key={index}><p className="service-description">{entry.body}</p><small>{personName(entry.authorId)} · {when(entry.createdAt)}</small></div>)}
        </section>}

        <section className="service-panel">
            <div className="service-section-heading"><h3>Timeline</h3><span>{incident.timeline.length} entries</span></div>
            <ol className="incident-timeline">{incident.timeline.map((entry, index) => <li key={index}><div className="incident-timeline-mark" aria-hidden="true" /><div><strong>{entry.kind.replace(/_/g, " ").toLowerCase()}</strong><p className="service-description">{entry.message}</p><small>{entry.actorId ? personName(entry.actorId) : "System"} · {when(entry.at)}</small></div></li>)}</ol>
        </section>

        {escalating && <EscalateDialog incident={incident} owners={owners} personName={personName} onClose={() => setEscalating(false)} onEscalate={async (body) => {
            setError(""); onBusyChange(true);
            try { onChange(await incidentApi.escalate(incident._id, body)); }
            finally { onBusyChange(false); }
        }} />}
    </>;
}

export function IncidentsView({ activeProfile, onBusyChange }) {
    const [rows, setRows] = useState([]);
    const [services, setServices] = useState([]);
    const [owners, setOwners] = useState([]);
    const [selected, setSelected] = useState(null);
    const [mode, setMode] = useState("list");
    const [filter, setFilter] = useState("ALL");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const generation = useRef(0);

    const load = async () => {
        const ticket = ++generation.current; setLoading(true); setError("");
        try {
            const [incidents, serviceRows, people] = await Promise.all([incidentApi.list(), serviceApi.list(), profileApi.list()]);
            if (ticket === generation.current) { setRows(incidents); setServices(serviceRows); setOwners(people); }
        } catch (failure) { if (ticket === generation.current) setError(message(failure)); }
        finally { if (ticket === generation.current) setLoading(false); }
    };
    useEffect(() => { load(); return () => { generation.current++; }; }, []);

    const serviceName = (id) => services.find((service) => service._id === id)?.name || "Unknown service";
    const personName = (id) => owners.find((person) => person._id === id)?.name || "Unavailable user";

    const open = async (id) => {
        setMode("detail"); setSelected(null); setLoading(true); setError("");
        try { setSelected(await incidentApi.get(id)); }
        catch (failure) { setError(message(failure)); }
        finally { setLoading(false); }
    };
    const back = () => { onBusyChange(false); setMode("list"); setSelected(null); setError(""); load(); };
    const create = async (body) => { const created = await incidentApi.create(body); setSelected(created); setMode("detail"); setError(""); };

    const visible = rows.filter((incident) => filter === "ALL" || incident.status === filter);

    return <main className="services-main">
        <div className="service-eyebrow">WORKSPACE / INCIDENTS</div>
        <div className="service-page-heading">
            <div><h1>{mode === "create" ? "Create incident" : mode === "detail" ? selected?.reference || "Incident" : "Incidents"}</h1>
                <p>{mode === "create" ? "Open an incident manually and set its first responder." : mode === "detail" ? "Coordinate the response and keep the timeline complete." : "Track every active and resolved incident across your services."}</p></div>
            {mode === "list"
                ? <button className="service-primary" disabled={loading && !error} onClick={() => { setError(""); setMode("create"); }}>+ Create incident</button>
                : <button onClick={back}>← All incidents</button>}
        </div>

        {error && <div className="service-alert error" role="alert">{error} {mode === "list" && <button onClick={load}>Retry</button>}{mode === "detail" && !selected && <button onClick={back}>Return to incidents</button>}</div>}

        {mode === "create" ? <IncidentForm services={services} owners={owners} defaultServiceId={rows[0]?.serviceId} onCreate={create} onCancel={back} onBusyChange={onBusyChange} />
            : mode === "detail" ? (loading || !selected ? !error && <div className="service-panel service-empty" role="status">Loading incident…</div>
                : <IncidentDetail incident={selected} owners={owners} serviceName={serviceName} personName={personName} onChange={setSelected} onBusyChange={onBusyChange} />)
            : loading ? <div className="service-panel service-empty" role="status">Loading incidents…</div>
                : <>
                    <div className="service-section-heading"><h2>Incident directory</h2>
                        <label className="incident-filter">Status<select value={filter} onChange={(e) => setFilter(e.target.value)}>{STATUS_FILTERS.map((value) => <option key={value} value={value}>{value === "ALL" ? "All statuses" : STATUS_LABELS[value]}</option>)}</select></label>
                    </div>
                    {rows.length === 0 && !error ? <div className="service-panel service-empty"><h2>No incidents yet</h2><p>Create an incident manually, or send a test event from a service to open one automatically.</p><button className="service-primary" onClick={() => setMode("create")}>Create your first incident</button></div>
                        : visible.length === 0 ? <div className="service-panel service-empty"><p>No {STATUS_LABELS[filter]?.toLowerCase()} incidents.</p></div>
                            : <div className="incident-list">{visible.map((incident) => <button className="incident-card" key={incident._id} onClick={() => open(incident._id)}>
                                <div className="incident-card-top"><span className="incident-ref">{incident.reference}</span><StatusChip value={incident.status} /></div>
                                <h2>{incident.title}</h2>
                                <div className="incident-card-meta"><SeverityChip value={incident.severity} /><span>{serviceName(incident.serviceId)}</span></div>
                                <dl><div><dt>Assignee</dt><dd>{incident.assigneeId ? personName(incident.assigneeId) : "Unassigned"}</dd></div><div><dt>Events</dt><dd>{incident.eventCount}</dd></div><div><dt>Opened</dt><dd>{when(incident.createdAt)}</dd></div></dl>
                            </button>)}</div>}
                </>}
    </main>;
}
