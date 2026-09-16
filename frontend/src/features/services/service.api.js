import { request } from "../../shared/api/client.js";

export const serviceApi = {
    list: () => request("/services"),
    get: (id) => request(`/services/${encodeURIComponent(id)}`),
    create: (body) => request("/services", { method: "POST", body: JSON.stringify(body) }),
    update: (id, body) => request(`/services/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }),
    remove: (id) => request(`/services/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
