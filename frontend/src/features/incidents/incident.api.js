import { request } from "../../shared/api/client.js";

const base = (id) => `/incidents/${encodeURIComponent(id)}`;
const post = (path, body) => request(path, { method: "POST", body: JSON.stringify(body ?? {}) });

export const incidentApi = {
    list: () => request("/incidents"),
    get: (id) => request(base(id)),
    create: (body) => post("/incidents", body),
    claim: (id) => post(`${base(id)}/claim`),
    assign: (id, assigneeId) => post(`${base(id)}/assign`, { assigneeId }),
    acknowledge: (id) => post(`${base(id)}/acknowledge`),
    addNote: (id, body) => post(`${base(id)}/notes`, { body }),
    escalate: (id, body) => post(`${base(id)}/escalate`, body),
    resolve: (id, resolutionNote) => post(`${base(id)}/resolve`, { resolutionNote }),
    step: (id, order, completed) => post(`${base(id)}/steps/${order}`, { completed }),
};
