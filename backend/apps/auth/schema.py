from apps.shared.validation import Errors, is_object_id, read_email, read_string

MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_LENGTH = 200


def validate_login(body):
    errors = Errors()
    email = read_email(errors, body, "email", MAX_EMAIL_LENGTH)
    password = read_string(errors, body, "password", minimum=1, maximum=MAX_PASSWORD_LENGTH)

    errors.raise_if_any()

    return email, password


def validate_switch_profile(body):
    errors = Errors()
    profile_id = read_string(errors, body, "profileId")

    if profile_id is not None and not is_object_id(profile_id):
        errors.add("profileId", "Select a valid profile.")

    errors.raise_if_any()

    return profile_id
