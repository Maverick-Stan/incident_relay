import { MaterialIcon } from "../../shared/components/MaterialIcon.jsx";
import { ProfileAvatar } from "./ProfileAvatar.jsx";

export function ProfilePicker({ error = "", loading = false, onLogout, onRetry, onSelect, profiles = [], switchingFrom = null }) {
    return <main className="profile-picker-page">
        <section className="profile-picker-card" aria-labelledby="profile-picker-title">
            <div className="profile-picker-mark"><span className="brand-date"><span className="brand-binding" />31</span></div>
            <h1 id="profile-picker-title">Choose an account</h1>
            <p className="profile-picker-subtitle">to continue to Incident Relay</p>
            {switchingFrom && <p className="profile-picker-current">Signed in as {switchingFrom.name}</p>}
            {loading && <div className="profile-picker-status" role="status"><span className="profile-loader" />Loading accounts…</div>}
            {!loading && error && <div className="profile-picker-error" role="alert"><div><strong>Accounts couldn’t be loaded</strong><span>{error}</span></div><button onClick={onRetry}>Try again</button></div>}
            {!loading && !error && <ul className="profile-account-list">
                {profiles.map((profile) => <li key={profile._id}>
                    <button className="profile-account" onClick={() => onSelect(profile)} aria-label={`Continue as ${profile.name}`}>
                        <ProfileAvatar profile={profile} size="small" />
                        <span><strong>{profile.name}</strong><small>{profile.email}</small></span>
                    </button>
                </li>)}
                <li>
                    <button className="profile-account profile-account-signout" onClick={onLogout}>
                        <span className="profile-account-icon"><MaterialIcon size={20}>logout</MaterialIcon></span>
                        <span><strong>Sign out of workspace</strong></span>
                    </button>
                </li>
            </ul>}
            {!loading && !error && profiles.length === 0 && <div className="profile-picker-status">{switchingFrom ? "No other accounts are available." : "No accounts are available."}</div>}
        </section>
        <footer className="workspace-login-footer"><span>English (United States)</span><span>Privacy</span><span>Terms</span></footer>
    </main>;
}
