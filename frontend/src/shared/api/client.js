const baseUrl = import.meta.env.VITE_API_URL || "/api/v1";
let sessionToken = localStorage.getItem("calendar-session-token") || "";
let profileToken = localStorage.getItem("calendar-profile-token") || "";

export function setSessionToken(token) {
    sessionToken = token || "";
    if (sessionToken) localStorage.setItem("calendar-session-token", sessionToken);
    else localStorage.removeItem("calendar-session-token");
}

export function setProfileToken(token) {
    profileToken = token || "";
    if (profileToken) localStorage.setItem("calendar-profile-token", profileToken);
    else localStorage.removeItem("calendar-profile-token");
}

export const hasSessionToken = () => Boolean(sessionToken || profileToken);
export const hasProfileToken = () => Boolean(profileToken);

export async function request(path, options = {}) {
    const { anonymous = false, ...fetchOptions } = options;
    const response = await fetch(`${baseUrl}${path}`, {
        ...fetchOptions,
        headers: {
            "Content-Type": "application/json",
            ...(!anonymous && (profileToken || sessionToken) ? { Authorization: `Bearer ${profileToken || sessionToken}` } : {}),
            ...options.headers,
        },
    });
    if (response.status === 204) return null;
    const contentType = response.headers?.get?.("content-type") || "";
    const payload = contentType.includes("application/json") || !response.headers
        ? await response.json()
        : null;
    if (!response.ok) {
        const code = payload?.error?.code;
        const message = payload?.error?.message || `Incident Relay service returned ${response.status}.`;
        if (response.status === 401 && ["AUTH_REQUIRED", "INVALID_TOKEN", "ACCOUNT_UNAVAILABLE"].includes(code)) {
            setProfileToken(""); setSessionToken(""); localStorage.removeItem("calendar-profile-id");
            window.dispatchEvent(new CustomEvent("calendar-session-expired", { detail: message }));
        }
        const error = new Error(message);
        error.status = response.status;
        error.code = code;
        error.details = payload?.error?.details;
        throw error;
    }
    if (!payload || !("data" in payload)) throw new Error("Incident Relay service returned an invalid response.");
    return payload.data;
}
