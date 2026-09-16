import { request } from "../../shared/api/client.js";

export const profileApi = {
    list: () => request("/profiles"),
};
