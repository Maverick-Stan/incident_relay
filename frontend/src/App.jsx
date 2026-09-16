import { Workspace } from "./features/Workspace.jsx";
import { useCallback, useEffect, useState } from "react";
import { profileApi } from "./features/profiles/profile.api.js";
import { ProfilePicker } from "./features/profiles/ProfilePicker.jsx";
import { authApi } from "./features/auth/auth.api.js";
import { WorkspaceLogin } from "./features/auth/WorkspaceLogin.jsx";
import { hasProfileToken, hasSessionToken, setProfileToken, setSessionToken } from "./shared/api/client.js";

function AppBootScreen() {
    return <main className="app-boot" aria-label="Opening Incident Relay" role="status">
        <div className="app-boot-brand"><strong>Incident Relay</strong></div>
        <div className="app-boot-progress" aria-hidden="true"><span /></div>
    </main>;
}

export default function App() {
    const [account, setAccount] = useState(null);
    const [authLoading, setAuthLoading] = useState(false);
    const [bootstrapping, setBootstrapping] = useState(true);
    const [authError, setAuthError] = useState("");
    const [profiles, setProfiles] = useState(null);
    const [profileError, setProfileError] = useState("");
    const [selectedProfileId, setSelectedProfileId] = useState(() => localStorage.getItem("calendar-profile-id") || "");
    const [switchingFrom, setSwitchingFrom] = useState("");
    const loadProfiles = useCallback(async () => {
        try { setProfileError(""); setProfiles(await profileApi.list()); }
        catch (error) { setProfileError(error.message); setProfiles([]); }
    }, []);
    useEffect(() => {
        const expire = (event) => { setProfileToken(""); setSessionToken(""); localStorage.removeItem("calendar-profile-id"); setSelectedProfileId(""); setAccount(null); setProfiles(null); setAuthError(event.detail || "Your Incident Relay session has expired."); };
        window.addEventListener("calendar-session-expired", expire);
        return () => window.removeEventListener("calendar-session-expired", expire);
    }, []);
    useEffect(() => {
        let active = true;
        const restore = async () => {
            if (!hasSessionToken()) { if (active) setBootstrapping(false); return; }
            let restoredSession = null;
            let restoreError = null;
            try {
                restoredSession = await authApi.session();
            } catch (error) {
                restoreError = error;
                if (hasProfileToken()) {
                    setProfileToken("");
                    localStorage.removeItem("calendar-profile-id");
                    try { restoredSession = await authApi.session(); restoreError = null; }
                    catch (sessionError) { restoreError = sessionError; }
                }
            }
            if (!active) return;
            if (!restoredSession) {
                setProfileToken(""); setSessionToken(""); localStorage.removeItem("calendar-profile-id");
                setAuthError(restoreError?.message || "Your Incident Relay session has expired.");
                setBootstrapping(false);
                return;
            }
            let restoredProfiles = [];
            let restoredProfileError = "";
            try { restoredProfiles = await profileApi.list(); }
            catch (profileRequestError) { restoredProfileError = profileRequestError.message; }
            if (!active) return;
            setAccount(restoredSession.account);
            setProfiles(restoredProfiles);
            setAuthError("");
            setProfileError(restoredProfileError);
            setBootstrapping(false);
        };
        restore();
        return () => { active = false; };
    }, []);
    const activeProfile = profiles?.find((profile) => String(profile._id) === selectedProfileId);
    useEffect(() => {
        if (profiles === null) return;
        if (selectedProfileId && !activeProfile) {
            localStorage.removeItem("calendar-profile-id");
            setProfileToken("");
            setSelectedProfileId("");
        }
    }, [activeProfile, profiles, selectedProfileId]);
    const login = async (email, password) => {
        try {
            setAuthLoading(true); setAuthError("");
            const result = await authApi.login(email, password);
            setSessionToken(result.token);
            let discoveredProfiles = [];
            try { setProfileError(""); discoveredProfiles = await profileApi.list(); }
            catch (profileRequestError) { setProfileError(profileRequestError.message); }
            setProfiles(discoveredProfiles);
            setAccount(result.account);
            const own = discoveredProfiles.find((profile) => profile.email === result.account.email);
            if (own) await selectProfile(own);
        }
        catch (error) { setAuthError(error.message); }
        finally { setAuthLoading(false); }
    };
    const logout = async () => {
        try { if (hasSessionToken()) await authApi.logout(); } catch {}
        setProfileToken(""); setSessionToken(""); localStorage.removeItem("calendar-profile-id"); setSelectedProfileId(""); setSwitchingFrom(""); setAccount(null); setProfiles(null); setAuthError("");
    };
    const selectProfile = async (profile) => {
        try {
            setProfileError("");
            const result = await authApi.switchProfile(profile._id);
            setProfileToken(result.token);
            localStorage.setItem("calendar-profile-id", profile._id);
            setSelectedProfileId(String(profile._id));
            setSwitchingFrom("");
        } catch (error) { setProfileError(error.message); }
    };
    if (bootstrapping) return <AppBootScreen />;
    if (!account) return <WorkspaceLogin error={authError} loading={authLoading} onLogin={login} />;
    if (activeProfile) {
        return <Workspace activeProfile={activeProfile} key={activeProfile._id} onLogout={logout} onSwitchProfile={() => { setSwitchingFrom(selectedProfileId); localStorage.removeItem("calendar-profile-id"); setProfileToken(""); setSelectedProfileId(""); }} />;
    }
    return <ProfilePicker error={profileError} loading={profiles === null} onLogout={logout} onRetry={loadProfiles} profiles={(profiles || []).filter((profile) => String(profile._id) !== switchingFrom)} onSelect={selectProfile} switchingFrom={profiles?.find((profile) => String(profile._id) === switchingFrom)} />;
}
