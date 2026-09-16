import { useState } from "react";

export function WorkspaceLogin({ error = "", loading = false, onLogin = () => {} }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const submit = (event) => { event.preventDefault(); onLogin(email.trim(), password); };
    return <main className="workspace-login-page">
        <section className="workspace-login-card" aria-labelledby="workspace-login-title">
            <div className="workspace-login-mark"><span className="brand-date"><span className="brand-binding" />31</span></div>
            <h1 id="workspace-login-title">Sign in</h1>
            <p className="workspace-login-subtitle">to continue to Incident Relay</p>
            <form onSubmit={submit}>
                <div className="outlined-input">
                    <input autoComplete="username" data-testid="email-input" disabled={loading} id="workspace-email" inputMode="email" placeholder=" " required type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
                    <label htmlFor="workspace-email">Email</label>
                </div>
                <div className="outlined-input">
                    <input autoComplete="current-password" className="workspace-password-input" data-testid="password-input" disabled={loading} id="workspace-password" name="password" placeholder=" " required type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                    <label htmlFor="workspace-password">Password</label>
                </div>
                {error && <p className="workspace-login-error" role="alert">{error}</p>}
                <div className="workspace-login-actions">
                    <button className="primary-button" disabled={loading} type="submit">{loading ? "Signing in…" : "Next"}</button>
                </div>
            </form>
        </section>
        <footer className="workspace-login-footer"><span>English (United States)</span><span>Privacy</span><span>Terms</span></footer>
    </main>;
}
