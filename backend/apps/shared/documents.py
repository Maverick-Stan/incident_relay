from datetime import datetime, timezone

from mongoengine import DateTimeField, Document


def now_utc():
    return datetime.now(timezone.utc)


def stamp(document):
    moment = now_utc()

    if document.created_at is None:
        document.created_at = moment

    document.updated_at = moment

    return document


class TimestampedDocument(Document):
    meta = {"abstract": True}

    created_at = DateTimeField(db_field="createdAt")
    updated_at = DateTimeField(db_field="updatedAt")

    def save(self, *args, **kwargs):
        stamp(self)

        return super().save(*args, **kwargs)
