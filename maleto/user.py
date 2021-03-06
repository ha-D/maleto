import logging
from datetime import datetime

from maleto.core import metrics, sentry
from maleto.core.bot import trace
from maleto.core.model import Model

logger = logging.getLogger(__name__)


class User(Model):
    class Meta:
        name = "users"
        fields = (
            "username",
            "first_name",
            "last_name",
            "chats",
            "lang",
            "chat_settings_message",
        )

    def __init__(self, **kwargs):
        super().__init__(**{"chats": [], **kwargs})

    def __str__(self):
        return f"User [{self.id}] {self.username}"

    def __repr__(self):
        return str(self)

    @classmethod
    @trace
    def create_or_update_from_api(cls, user, lang=None):
        if user is not None:
            # Don't set the lang if its the default lang (i.e, `en`) so that it
            # could be overriden in other places (e.g, by a chat's lang). The user
            # can set their lang to `en` manually to change this behaviour
            if lang is None and user.language_code != "en":
                lang = user.language_code

            d = cls.col().find_one_and_update(
                {"_id": user.id},
                {
                    "$set": {
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "updated_at": datetime.now(),
                    },
                    "$setOnInsert": {"created_at": datetime.now(), "lang": lang},
                },
                upsert=True,
            )
            if d is None:
                sentry.set_span_tag("created", True)
                logger.info(
                    f"New user created",
                    extra=dict(
                        user=user.id,
                        username=user.username,
                        fullname=f"{user.first_name or ''} {user.last_name or ''}",
                    ),
                )
                metrics.user_create.inc()
                return User.find_by_id(user.id)
            else:
                sentry.set_span_tag("created", False)
                return cls(**d)
        return None

    def link(self):
        name = self.username
        if not name:
            name = f'{self.first_name or ""} {self.last_name or ""}'
        return f"[@{name}](tg://user?id={self.id})"
