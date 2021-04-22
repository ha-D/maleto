import logging
from datetime import datetime

from pymongo.collection import ReturnDocument

from .utils.model import Model

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

    @classmethod
    def create_or_update_from_api(cls, user):
        if user is not None:
            d = cls.col().find_one_and_update(
                {"_id": user.id},
                {
                    "$set": {
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "updated_at": datetime.now(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(),
                        "lang": user.language_code,
                    },
                },
                upsert=True,
            )
            if d is None:
                logger.info(
                    f"New user created. user:{user.id} username:{user.username} name:{user.first_name or ''} {user.last_name or ''}"
                )
                return User.find_by_id(user.id)
            else:
                return cls(**d)
        return None

    def link(self):
        name = self.username
        if not name:
            name = f'{self.first_name or ""} {self.last_name or ""}'
        return f"[@{name}](tg://user?id={self.id})"
