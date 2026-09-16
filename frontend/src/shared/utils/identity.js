export function identityInitials(name = "") {
    const parts = String(name).trim().split(/\s+/).filter(Boolean);
    if (parts.length > 1 && /^\d+$/.test(parts.at(-1))) {
        return `${parts[0][0]}${Number(parts.at(-1))}`.toUpperCase();
    }
    return parts.slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}
