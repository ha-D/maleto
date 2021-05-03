import logging
from datetime import datetime

from maleto.core import metrics, sentry
from maleto.core.bot import trace
from maleto.core.lang import _, uselang
from maleto.core.model import Model

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
            "next_index",
        )

    def __init__(self, **kwargs):
        super().__init__(**{"admins": [], "next_index": 1, **kwargs})

    def __str__(self):
        return f"Chat [{self.id}] {self.title}"

    def __repr__(self):
        return str(self)

    @trace
    def publish_info_message(self, context):
        if self.info_message_id is None:
            info_msg = context.bot.send_message(
                chat_id=self.id,
                text=self.generate_info_message(),
            )
            self.info_message_id = info_msg.message_id
            info_msg.pin(disable_notification=True)
            self.save()
        else:
            context.bot.edit_message_text(
                chat_id=self.id,
                message_id=self.info_message_id,
                text=self.generate_info_message(),
            )

    @trace
    def generate_info_message(self):
        from maleto.item import Item

        with uselang(self.lang):
            items = Item.find(posts__chat_id=self.id)
            s = "\n".join(
                [
                    _("Items on sale:"),
                    "",
                    *[item.chat_link(self.id) for item in items],
                    "",
                    "",
                    _("*Frequently Asked Questions:*"),
                    "",
                    _("*What is this?*"),
                    " ".join(
                        [
                            _("These items are on sale by the members of this group."),
                            _(
                                "The sale is performed through an auction, you can place a bid on any item you like."
                            ),
                            _(
                                "The bid with the highest price will be the buyer of that item."
                            ),
                        ]
                    ),
                    "",
                    _("*How can I place a bid?*"),
                    " ".join(
                        [
                            _("Below each item is a purchase link."),
                            _(
                                "Click on the link and you will be redirected to the Bot."
                            ),
                            _(
                                "Click on the Start button and follow the steps to place a bid."
                            ),
                        ]
                    ),
                    "",
                    _("*Can I add items for sale?*"),
                    " ".join(
                        [
                            _(
                                "This is an open channel, all joined members can add items."
                            ),
                            _(
                                "To add an item first join this channel, then [click here](https://t.me/MaletoBot) to go to the Bot."
                            ),
                            _(
                                "Enter the `/newitem` command and follow the steps to create a new item."
                            ),
                        ]
                    ),
                    "",
                    _("*Can I use this in other groups or channels?*"),
                    " ".join(
                        [
                            _("Yup, you can use MaletoBot anywhere you like."),
                            _("Just add the Bot to your group or channel."),
                            _(
                                "All members of the group will be able to publish items to the chat."
                            ),
                        ]
                    ),
                    "",
                    _(
                        "*I found a bug or have a feature suggestion, what should I do?*"
                    ),
                    " ".join(
                        [
                            _(
                                "MaletoBot is an open source project and under development."
                            ),
                            _(
                                "If you've encountered a bug, have suggestions or want to contribute visit our [Github Page](https://github.com/ha-D/maleto)"
                            ),
                        ]
                    ),
                ]
            )
            return s

    @classmethod
    def get_chat_names(cls, chat_ids):
        chats = Chat.find(_id={"$in": chat_ids})
        return {c.id: c.title for c in chats}

    @classmethod
    @trace
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
                sentry.set_span_tag("created", True)
                logger.info(
                    f"New chat created. chat:{api_chat.id} title:{api_chat.title}"
                )
                chat = Chat.find_by_id(api_chat.id)
                chat.publish_info_message(context)
                metrics.chat_create.inc()
                return chat
            else:
                sentry.set_span_tag("created", False)
                return cls(**d)
        return None
