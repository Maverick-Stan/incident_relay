import { request } from "../../shared/api/client.js";
export const eventApi = {
    history: (id, offset = 0) => request(`/services/${encodeURIComponent(id)}/events?offset=${offset}`),
    send: (id, key, body) => request(`/services/${encodeURIComponent(id)}/events`, { method: "POST", anonymous: true, headers: { "X-Integration-Key": key }, body: JSON.stringify(body) }),
    incident: (id) => request(`/incidents/${encodeURIComponent(id)}`),
};
