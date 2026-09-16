import { useState } from "react";
import { CommandCenter } from "./command/CommandCenter.jsx";
import { ServicesView } from "./services/ServicesWorkspace.jsx";
import { IncidentsView } from "./incidents/IncidentsWorkspace.jsx";
import { AnalyticsView } from "./analytics/AnalyticsView.jsx";
import { IncidentLinkPreview } from "./events/ServiceEvents.jsx";

export function Workspace({ activeProfile, onLogout, onSwitchProfile }) {
    const [section, setSection] = useState("overview");
    const [busy, setBusy] = useState(false);
    const go = (next) => { if (!busy && next !== section) { setBusy(false); setSection(next); } };
    const tab = (id, label) => <button className={section === id ? "is-active" : ""} aria-current={section === id ? "page" : undefined} disabled={busy} onClick={() => go(id)}>{label}</button>;
    const body = () => {
        switch (section) {
            case "services": return <ServicesView key={`services-${activeProfile._id}`} activeProfile={activeProfile} onBusyChange={setBusy} />;
            case "incidents": return <IncidentsView key={`incidents-${activeProfile._id}`} activeProfile={activeProfile} onBusyChange={setBusy} />;
            case "analytics": return <AnalyticsView key={`analytics-${activeProfile._id}`} />;
            default: return <CommandCenter key={`overview-${activeProfile._id}`} onBusyChange={setBusy} />;
        }
    };
    return <div className="relay-workspace">
        <header className="relay-topbar">
            <div className="relay-topbar-lead">
                <a href="#" className="relay-brand" onClick={(e) => { e.preventDefault(); go("overview"); }}><span aria-hidden="true">↗</span> Incident Relay</a>
                <nav className="relay-nav" aria-label="Workspace sections">{tab("overview", "Command Center")}{tab("incidents", "Incidents")}{tab("services", "Services")}{tab("analytics", "Analytics")}</nav>
            </div>
            <div className="service-actions"><span className="relay-profile">{activeProfile.name}</span><button disabled={busy} onClick={onSwitchProfile}>Switch profile</button><button disabled={busy} onClick={onLogout}>Sign out</button></div>
        </header>
        {body()}
        <IncidentLinkPreview />
    </div>;
}
