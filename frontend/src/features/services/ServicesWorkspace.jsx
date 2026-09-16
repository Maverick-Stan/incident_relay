import { useEffect, useRef, useState } from "react";
import { serviceApi } from "./service.api.js";
import { profileApi } from "../profiles/profile.api.js";
import { ServiceEvents } from "../events/ServiceEvents.jsx";
import "./services.css";

const emptyService = (ownerId) => ({ name: "", description: "", ownerId, defaultSeverity: "HIGH", groupingWindowMinutes: 30, workflowTemplate: [] });
const message = (error) => {
    const fields = error.details?.fieldErrors;
    return fields ? Object.entries(fields).map(([field, errors]) => `${field}: ${errors.join(" ")}`).join(" ") : error.message;
};

function ServiceForm({ initial, owners, onSave, onCancel, onBusyChange }) {
    const [form, setForm] = useState(initial);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const errorRef = useRef(null);
    const set = (field, value) => setForm((current) => ({ ...current, [field]: value }));
    const step = (index, field, value) => set("workflowTemplate", form.workflowTemplate.map((row, i) => i === index ? { ...row, [field]: value } : row));
    const move = (index, direction) => {
        const rows = [...form.workflowTemplate];
        [rows[index], rows[index + direction]] = [rows[index + direction], rows[index]];
        set("workflowTemplate", rows);
    };
    const submit = async (event) => {
        event.preventDefault(); setSaving(true); onBusyChange(true); setError("");
        try {
            await onSave({ name: form.name.trim(), description: form.description.trim(), ownerId: form.ownerId,
                defaultSeverity: form.defaultSeverity, groupingWindowMinutes: Number(form.groupingWindowMinutes),
                workflowTemplate: form.workflowTemplate.map((row, i) => ({ ...row, title: row.title.trim(), instructions: row.instructions.trim(), order: i + 1 })) });
        } catch (failure) { setError(message(failure)); setTimeout(() => errorRef.current?.focus(), 0); }
        finally { setSaving(false); onBusyChange(false); }
    };
    return <form className="service-form" onSubmit={submit}>
        {error && <div className="service-alert error" role="alert" tabIndex={-1} ref={errorRef}>{error}</div>}
        <fieldset disabled={saving}>
            <div className="service-form-grid">
                <label>Service name<input autoFocus required maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Checkout API" /></label>
                <label>Owner<select required value={form.ownerId} onChange={(e) => set("ownerId", e.target.value)}><option value="">Choose an owner</option>{owners.map((owner) => <option key={owner._id} value={owner._id}>{owner.name}</option>)}</select></label>
                <label className="service-span">Description<textarea maxLength={2000} rows={3} value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What does this service do?" /></label>
                <label>Default severity<select value={form.defaultSeverity} onChange={(e) => set("defaultSeverity", e.target.value)}>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((severity) => <option key={severity}>{severity}</option>)}</select></label>
                <label>Grouping window (minutes)<input type="number" required min={1} max={1440} step={1} value={form.groupingWindowMinutes} onChange={(e) => set("groupingWindowMinutes", e.target.value)} /><small>Related events can join an active incident within this window.</small></label>
            </div>
            <div className="service-section-heading"><div><h3>Response workflow</h3><p>Steps run in order. Existing incident snapshots stay unchanged.</p></div><span>{form.workflowTemplate.length}/20 steps</span></div>
            {form.workflowTemplate.length === 0 && <p className="service-muted">No steps yet. Add guidance for your responders, or keep the template empty.</p>}
            {form.workflowTemplate.map((row, index) => <section className="service-step-editor" key={index} aria-label={`Step ${index + 1}`}>
                <div className="service-step-heading"><strong>Step {index + 1}</strong><div className="service-actions">
                    <button type="button" disabled={index === 0} aria-label={`Move step ${index + 1} up`} onClick={() => move(index, -1)}>↑</button>
                    <button type="button" disabled={index === form.workflowTemplate.length - 1} aria-label={`Move step ${index + 1} down`} onClick={() => move(index, 1)}>↓</button>
                    <button type="button" onClick={() => set("workflowTemplate", form.workflowTemplate.filter((_, i) => i !== index))}>Remove step {index + 1}</button>
                </div></div>
                <label>Step {index + 1} title<input required maxLength={160} value={row.title} onChange={(e) => step(index, "title", e.target.value)} /></label>
                <label>Step {index + 1} instructions<textarea required rows={2} maxLength={2000} value={row.instructions} onChange={(e) => step(index, "instructions", e.target.value)} /></label>
                <label className="service-check"><input type="checkbox" checked={row.required} onChange={(e) => step(index, "required", e.target.checked)} />Required before resolution</label>
            </section>)}
            <button type="button" disabled={form.workflowTemplate.length >= 20} onClick={() => set("workflowTemplate", [...form.workflowTemplate, { title: "", instructions: "", required: true }])}>+ Add workflow step</button>
            <div className="service-form-footer"><button type="button" onClick={onCancel}>Cancel</button><button className="service-primary" type="submit">{saving ? "Saving…" : initial._id ? "Save changes" : "Create service"}</button></div>
        </fieldset>
    </form>;
}

export function ServicesView({ activeProfile, onBusyChange }) {
    const [rows, setRows] = useState([]);
    const [owners, setOwners] = useState([]);
    const [selected, setSelected] = useState(null);
    const [mode, setMode] = useState("list");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [key, setKey] = useState("");
    const [copied, setCopied] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [saving, setSaving] = useState(false);
    const generation = useRef(0);
    const load = async () => {
        const ticket = ++generation.current;
        setLoading(true); setError("");
        try { const [services, people] = await Promise.all([serviceApi.list(), profileApi.list()]); if (ticket === generation.current) { setRows(services); setOwners(people); } }
        catch (failure) { if (ticket === generation.current) setError(message(failure)); }
        finally { if (ticket === generation.current) setLoading(false); }
    };
    useEffect(() => { load(); return () => { generation.current++; }; }, []);
    useEffect(() => { onBusyChange(Boolean(key) || deleting || saving); }, [key, deleting, saving, onBusyChange]);
    const open = async (id) => {
        setMode("detail"); setSelected(null); setLoading(true); setError(""); setNotice(""); setConfirmDelete(false);
        try { setSelected(await serviceApi.get(id)); }
        catch (failure) { setError(message(failure)); }
        finally { setLoading(false); }
    };
    const back = () => { setKey(""); setMode("list"); setSelected(null); setConfirmDelete(false); load(); };
    const save = async (body) => {
        if (mode === "create") {
            const result = await serviceApi.create(body);
            setSelected(result.service); setKey(result.integrationKey); setCopied(false); setNotice("Service created. Save your integration key below.");
        } else { setSelected(await serviceApi.update(selected._id, body)); setNotice("Service updated. Existing incident workflows are unchanged."); }
        setError(""); setMode("detail");
    };
    const remove = async () => {
        setDeleting(true); setError(""); setNotice("");
        try { await serviceApi.remove(selected._id); setNotice("Service deleted."); back(); }
        catch (failure) { setError(message(failure)); setConfirmDelete(false); }
        finally { setDeleting(false); }
    };
    const ownerName = (id) => owners.find((person) => person._id === id)?.name || "Unavailable owner";
    return <main className="services-main">
            <div className="service-eyebrow">WORKSPACE / SERVICES</div>
            <div className="service-page-heading"><div><h1>{mode === "list" ? "Services" : mode === "create" ? "Create service" : mode === "edit" ? "Edit service" : selected?.name || "Service details"}</h1><p>{mode === "list" ? "Define ownership and give every response a starting point." : mode === "create" ? "Connect a service to its owner and response workflow." : "Service configuration and response guidance."}</p></div>
                {mode === "list" ? <button className="service-primary" disabled={loading || Boolean(error)} onClick={() => { setNotice(""); setMode("create"); }}>+ Create service</button> : <button disabled={Boolean(key) || deleting || saving} onClick={back}>← All services</button>}
            </div>
            {notice && <div className="service-alert success" role="status">{notice}</div>}
            {error && <div className="service-alert error" role="alert">{error} {mode === "list" && <button onClick={load}>Retry</button>} {mode === "detail" && !selected && <button onClick={back}>Return to services</button>}</div>}
            {loading ? <div className="service-panel service-empty" role="status">Loading services…</div> : mode === "list" ? <>
                <div className="service-section-heading"><h2>Service directory</h2><span>{rows.length} services</span></div>
                {rows.length === 0 && !error ? <div className="service-panel service-empty"><h2>No services yet</h2><p>Create your first service to establish ownership and a response workflow.</p><button className="service-primary" onClick={() => setMode("create")}>Create your first service</button></div> : <div className="service-directory">{rows.map((service) => <button className="service-card" key={service._id} onClick={() => open(service._id)}>
                    <div className="service-card-heading"><span className="service-avatar" aria-hidden="true">{service.name.slice(0, 2).toUpperCase()}</span><span className={`service-severity ${service.defaultSeverity.toLowerCase()}`}>{service.defaultSeverity}</span></div>
                    <h2>{service.name}</h2><p>{service.description || "No description provided."}</p><dl><div><dt>Owner</dt><dd>{ownerName(service.ownerId)}</dd></div><div><dt>Grouping</dt><dd>{service.groupingWindowMinutes} min</dd></div><div><dt>Workflow</dt><dd>{service.workflowTemplate.length} steps</dd></div></dl><span className="service-card-link">View service →</span>
                </button>)}</div>}
            </> : mode === "create" || mode === "edit" ? <div className="service-panel"><ServiceForm key={selected?._id || "new"} initial={mode === "create" ? emptyService(activeProfile._id) : selected} owners={owners} onBusyChange={setSaving} onSave={save} onCancel={() => selected ? setMode("detail") : back()} /></div> : selected && <>
                {key && <section className="service-key-panel" aria-labelledby="key-title"><h2 id="key-title">Save your integration key</h2><p>This key is shown once. Copy it now and store it securely. After dismissal, only its last four characters are available.</p><label>Integration key<input readOnly value={key} onFocus={(e) => e.target.select()} /></label><div className="service-actions"><button onClick={async () => { try { await navigator.clipboard.writeText(key); setCopied(true); } catch { setError("Copy was unavailable. Select the key and copy it manually."); } }}>{copied ? "Copied" : "Copy key"}</button><button className="service-primary" onClick={() => { setKey(""); setError(""); setNotice("Service created. Integration key dismissed."); }}>I’ve saved the key</button></div></section>}
                <section className="service-panel"><div className="service-section-heading"><h2>Configuration</h2><button disabled={Boolean(key) || deleting || saving} onClick={() => { setNotice(""); setError(""); setConfirmDelete(false); setMode("edit"); }}>Edit service</button></div><p className="service-description">{selected.description || "No description provided."}</p><dl className="service-facts"><div><dt>Owner</dt><dd>{ownerName(selected.ownerId)}</dd></div><div><dt>Default severity</dt><dd><span className={`service-severity ${selected.defaultSeverity.toLowerCase()}`}>{selected.defaultSeverity}</span></dd></div><div><dt>Grouping window</dt><dd>{selected.groupingWindowMinutes} minutes</dd></div><div><dt>Integration key</dt><dd>•••• {selected.integrationKeyLastFour}</dd></div></dl></section>
                <section className="service-panel"><div className="service-section-heading"><h2>Response workflow</h2><span>{selected.workflowTemplate.length} steps</span></div><p className="service-muted">Copied into each new incident. Responders complete steps in order.</p>{selected.workflowTemplate.length === 0 ? <p>No workflow steps configured.</p> : <ol className="service-workflow">{selected.workflowTemplate.map((row) => <li key={row.order}><div><strong>{row.title}</strong><span>{row.required ? "Required" : "Optional"}</span></div><p>{row.instructions}</p></li>)}</ol>}</section>
                <ServiceEvents key={selected._id} service={selected} disabled={Boolean(key) || deleting || saving} />
                <section className="service-panel service-danger"><h2>Delete service</h2><p>Only unused services can be deleted. Services with events or incidents must remain available.</p>{confirmDelete ? <div role="group" aria-label="Confirm service deletion"><p>Delete <strong>{selected.name}</strong>? This cannot be undone.</p><div className="service-actions"><button disabled={deleting} onClick={() => setConfirmDelete(false)}>Cancel</button><button className="service-delete" disabled={deleting} onClick={remove}>{deleting ? "Deleting…" : "Confirm deletion"}</button></div></div> : <button className="service-delete" disabled={Boolean(key)} onClick={() => { setNotice(""); setError(""); setConfirmDelete(true); }}>Delete service</button>}</section>
            </>}
    </main>;
}
