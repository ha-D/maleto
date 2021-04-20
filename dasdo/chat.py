from datetime import datetime
import logging

from telegram import *

from .utils.model import Model

logger = logging.getLogger(__name__)


class Chat(Model):
    class Meta:
        name = "chats"
        fields = (
            "title",
            "username",
            "type",
            "info_message_id",
            "active",
            "admins",
            "lang",
        )

    def __init__(self, **kwargs):
        super().__init__({"admins": [], **kwargs})

    def publish_info_message(self, context):
        if self.info_message_id is None:
            info_msg = context.bot.send_message(
                chat_id=self.id,
                text=self.generate_info_message(),
                parse_mode=ParseMode.MARKDOWN,
            )
            self.info_message_id = info_msg.message_id
            info_msg.pin(disable_notification=True)
        else:
            context.bot.edit_message_text(
                chat_id=self.id,
                message_id=self.info_message_id,
                text=self.generate_info_message(),
                parse_mode=ParseMode.MARKDOWN,
            )

    def generate_info_message(self):
        from .item import Item

        items = Item.find(posts__chat_id=self.id)
        s = "\n".join(
            [
                "Welcome!!",
                "",
                "These items are currently on sale:",
                *[item.chat_link(self.id) for item in items],
                "",
            ]
        )
        return s

    @classmethod
    def get_chat_names(cls, chat_ids):
        chats = Chat.find(_id__in=chat_ids)
        return {c.id: c.title for c in chats}

    @classmethod
    def create_or_update_from_api(cls, api_chat):
        if api_chat is not None:
            d = cls.col().find_one_and_update(
                {"_id": api_chat.id},
                {
                    "$set": {
                        "username": api_chat.username,
                        "title": api_chat.title,
                        "type": api_chat.type,
                        "last_name": api_chat.last_name,
                        "updated_at": datetime.now(),
                    },
                    "$setOnInsert": {
                        "created_at": datetime.now(),
                    },
                },
                upsert=True,
            )
            if d is not None:
                return cls(**d)
        return None
