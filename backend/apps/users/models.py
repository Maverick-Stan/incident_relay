from mongoengine import BooleanField, IntField, ListField, ObjectIdField, StringField

from apps.shared.documents import TimestampedDocument


class User(TimestampedDocument):
    meta = {"collection": "users", "indexes": [{"fields": ["email"], "unique": True}, "name"]}

    name = StringField(required=True, max_length=120)
    email = StringField(required=True, max_length=254)
    password_hash = StringField(db_field="passwordHash", required=True)
    allowed_profile_ids = ListField(ObjectIdField(), db_field="allowedProfileIds", default=list)
    active = BooleanField(default=True)
    avatar_color = StringField(db_field="avatarColor", required=True, regex=r"^#[0-9a-fA-F]{6}$")
    sort_order = IntField(db_field="sortOrder", default=0)
    time_zone = StringField(db_field="timeZone", default="UTC")
