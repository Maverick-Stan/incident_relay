from apps.shared.domain import identifier, require

from . import repository


def get(user_id):
    return require(repository.find(identifier(user_id, "userId")), "user")


def find_profile_by_id(profile_id):
    return repository.public_profile(identifier(profile_id, "profileId"))


def list_profiles(ids):
    return repository.list_profiles(ids or [])
