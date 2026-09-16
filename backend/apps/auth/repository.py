from bson import ObjectId

from apps.users import repository as users


def find_active_by_email(email):
    return users.find_login(email)


def find_active_by_id(account_id):
    return users.find_account(ObjectId(account_id))
