import logging
from datetime import datetime

from telegram import *

from dasdo.utils.lang import _, uselang
from dasdo.utils.model import Model

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
        super().__init__(**{"admins": [], **kwargs})

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
        from dasdo.item import Item
        with uselang(self.lang):
            items = Item.find(posts__chat_id=self.id)
            s = "\n".join(
                [
                    _("Items on sale:"),
                    "",
                    *[item.chat_link(self.id) for item in items],
                    "",
                ]
            )
            return s

    @classmethod
    def get_chat_names(cls, chat_ids):
        chats = Chat.find(_id={"$in": chat_ids})
        return {c.id: c.title for c in chats}

    @classmethod
    def create_or_update_from_api(cls, context, api_chat):
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
            if d is None:
                logger.info(
                    f"New chat created. chat:{api_chat.id} title:{api_chat.title}"
                )
                chat = Chat.find_by_id(api_chat.id)
                chat.publish_info_message(context)
                return chat
            else:
                return cls(**d)
        return None
