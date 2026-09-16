from .models import User

PUBLIC_FIELDS = ("id", "name", "email", "avatar_color", "sort_order", "time_zone")


def find(user_id):
    return User.objects(id=user_id, active=True).first()


def find_login(email):
    return User.objects(email=email, active=True).as_pymongo().first()


def find_account(user_id):
    return User.objects(id=user_id, active=True).as_pymongo().first()


def public_profile(user_id):
    return User.objects(id=user_id, active=True).only(*PUBLIC_FIELDS).as_pymongo().first()


def list_profiles(ids):
    return list(User.objects(id__in=ids, active=True).only(*PUBLIC_FIELDS).order_by("sort_order", "name").as_pymongo())


def insert(user):
    user.validate()
    User.objects.insert(user)
    return user
