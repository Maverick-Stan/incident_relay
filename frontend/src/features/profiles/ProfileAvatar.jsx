import { identityInitials } from "../../shared/utils/identity.js";

export function ProfileAvatar({ profile, size = "medium" }) {
    return <span className={`profile-avatar profile-avatar-${size}`} style={{ "--profile-color": profile.avatarColor }} aria-hidden="true">
        <span>{identityInitials(profile.name)}</span>
    </span>;
}
