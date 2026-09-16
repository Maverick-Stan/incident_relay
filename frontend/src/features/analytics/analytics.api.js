import { request } from "../../shared/api/client.js";

export const analyticsApi = {
    get: ({ since, until } = {}) => {
        const params = new URLSearchParams();
        if (since) params.set("since", since);
        if (until) params.set("until", until);
        const query = params.toString();
        return request(`/analytics${query ? `?${query}` : ""}`);
    },
};
