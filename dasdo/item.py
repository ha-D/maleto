import logging
import string
import random
import time

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.error import BadRequest

from .utils import find_best_inc, find_by, get_bot, translator
from .utils.model import Model
from .utils.currency import format_currency

logger = logging.getLogger(__name__)


class Item(Model):
    class Meta:
        name = "items"
        fields = (
            "active",
            "title",
            "description",
            "owner_id",
            "photos",
            "bids",
            "base_price",
            "posts",
            "min_price_inc",
            "settings_message",
            "bid_messages",
            "currency",
        )

    def __init__(self, **kwargs):
        super().__init__(
            **{
                "photos": [],
                "bids": [],
                "posts": [],
                "stores": [],
                "settings_message": [],
                "bid_messages": [],
                **kwargs,
            }
        )

    @classmethod
    def new(cls, owner_id):
        item = Item()
        item.owner_id = owner_id
        item.id = "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
        return item

    @classmethod
    def find(cls, **kwargs):
        return super().find(active=True, **kwargs)

    @property
    def owner(self):
        from .user import User

        return User.find_by_id(self.owner_id)

    def remove_user_bid(self, context, user_id, sort=True):
        for bid in self.bids:
            bid["users"] = [u for u in bid["users"] if u != user_id]
        self.bids = [b for b in self.bids if len(b["users"]) > 0]
        if sort:
            self._sort_bids()

    def add_user_bid(self, context, user_id, price, sort=True):
        # TODO: check min price inc

        _ = translator(context.lang)
        if self.base_price and price < self.base_price:
            raise ValueError(_("Your offer is too low"))

        min_price_inc = self.min_price_inc or find_best_inc(self.base_price)
        highest_bid = self.base_price
        if self.bids:
            highest_bid = max(self.bids, key=lambda b: b["price"])["price"]
        if price > highest_bid and price - highest_bid < min_price_inc:
            raise ValueError(
                _(
                    "You need to increase by at least {} if you want to offer a higher price"
                ).format(format_currency(context, self.currency, min_price_inc))
            )

        self.remove_user_bid(user_id, sort=False)
        self.bids.append({"user_id": user_id, "price": price, "ts": time.time()})
        if sort:
            self._sort_bids()

    def _sort_bids(self):
        self.bids = sorted(self.bids, key=lambda b: (b["price"], b["ts"]), reverse=True)

    def add_to_chat(self, context, chat_id):
        from .chat import Chat

        post, _ = find_by(self.posts, "chat_id", chat_id)
        if not post:
            media = [InputMediaPhoto(media=photo) for photo in self.photos]
            media[0].caption = self.generate_sale_message(context)
            media[0].parse_mode = parse_mode = ParseMode.MARKDOWN
            messages = context.bot.send_media_group(chat_id=chat_id, media=media)
            self.posts.append(
                {"chat_id": chat_id, "messages": [m.message_id for m in messages]}
            )
        # Need to save for the chat publish to work
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    def remove_from_chat(self, context, chat_id):
        from .chat import Chat

        post, idx = find_by(self.posts, "chat_id", chat_id)
        if post:
            for message_id in post["messages"]:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            del self.posts[idx]
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    def new_bid_message(self, context, user_id, message_id=None, publish=True):
        prev_mes, _ = find_by(self.bid_messages, "user_id", user_id)
        if prev_mes is not None:
            # Clear previous bid message for this user
            try:
                context.bot.edit_message_caption(
                    chat_id=prev_mes["user_id"],
                    message_id=prev_mes["message_id"],
                    caption=f"{self.title}",
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                pass

        _ = translator(context.lang)
        if message_id is None:
            message = context.bot.send_photo(
                chat_id=self.owner_id, photo=self.photos[0], caption=_("Please wait...")
            )
            message_id = message.message_id
        if prev_mes:
            prev_mes["message_id"] = message_id
        else:
            self.bid_messages.append({"user_id": user_id, "message_id": message_id})

    def new_settings_message(self, context, message_id=None, publish=True):
        prev_mes = self.settings_message
        if prev_mes is None:
            # Clear previous bid message for this user
            try:
                context.bot.edit_message_caption(
                    chat_id=self.owner_id,
                    message_id=prev_mes["message_id"],
                    caption=f"{self.title}",
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                pass
        _ = translator(context.lang)
        if message_id is None:
            message = context.bot.send_photo(
                chat_id=self.owner_id, photo=self.photos[0], caption=_("Please wait...")
            )
            message_id = message.message_id
        self.settings_message = {"message_id": message_id, "state": "default"}
        if publish:
            self.publish_settings_message(context)

    def update_bid_message_state(self, user_id, state):
        mes, _ = find_by(self.interaction_messages, "user_id", user_id)
        mes["state"] = state  # TODO: handle NONE

    def update_settings_message_state(self, state):
        mes = self.settings_message
        mes["state"] = state

    def publish(self, context):
        sale_message = self.generate_sale_message(context)
        for post in self.posts:
            chat_id = post["chat_id"]
            message_id = post["messages"][0]
            ignore_no_changes(
                context.bot.edit_message_caption,
                chat_id=int(chat_id),
                message_id=message_id,
                parse_mode=ParseMode.MARKDOWN_V2,
                caption=sale_message,
            )

        self.publish_settings_message(context)

        for mes in self.bid_messages:
            self.publish_interaction_message(
                context, self, mes["user_id"], mes["message_id"]
            )

    def publish_settings_message(self, context):
        from .item_settings import publish_settings_message

        return publish_settings_message(context, self)

    def publish_bid_message(self, context, user_id, message_id=None):
        from .item_bid import publish_bid_message

        return publish_bid_message(context, self, user_id, message_id)

    def get_bid_message(self, user_id):
        imes, _ = find_by(self.interaction_messages, "user_id", user_id)
        return imes

    def delete_all_messages(self, context):
        for bmes in self.bid_messages:
            try:
                user = User.find_by_id(bmes["user_id"])
                if user is None:
                    continue
                _ = translator(user.lang)
                msg = "\n".join([self.title, "", _("This item is no longer available")])
                context.bot.edit_message_caption(
                    chat_id=bmes["user_id"],
                    message_id=bmes["message_id"],
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                logger.warning(
                    "Unable to disable bid message (%d, %d)",
                    bmes["chat_id"],
                    bmes["message_id"],
                    exc_info=True,
                )

        if smes := self.settings_message:
            try:
                _ = translator(context.lang)
                msg = "\n".join([self.title, "", _("This item is no longer available")])
                context.bot.edit_message_caption(
                    chat_id=self.owner_id,
                    message_id=smes["message_id"],
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                logger.warning(
                    "Unable to disable settings message (%d, %d)",
                    smes["chat_id"],
                    smes["message_id"],
                    exc_info=True,
                )

        for post in self.posts:
            chat_id = post["chat_id"]
            for message_id in post["messages"]:
                try:
                    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                except BadRequest as e:
                    logger.warning(
                        "Unable to delete post message (%d, %d)",
                        chat_id,
                        message_id,
                        exc_info=True,
                    )

    def generate_sale_message(self, context):
        from .user import User

        bot = get_bot(context)

        _ = translator(context.lang)

        current_price = self.base_price
        if len(self.bids > 0):
            current_price = self.bids[0]["price"]

        msg = [
            f"*{self.title}*",
            _("Seller: {}").format(self.owner.link()),
            "",
            self.description,
            "",
            _("Price: {}").format(
                format_currency(context, self.currency, current_price)
            ),
        ]

        if len(self.bids) > 0:
            users = [User.find_by_id(uid) for uid in self.bids[-1]["users"]]
            msg += [_("Buyer: {}").format(users[0].link())]
            if len(users) > 1:
                users = users[1:]
                msg.append(_("Waiting List:"))
                if len(users) <= 4:
                    msg += [f"{i+1}. {u.link()}" for i, u in enumerate(users)]
                elif len(users) > 4:
                    msg += [f"{i+1}. {u.link()}" for i, u in enumerate(users[:3])]
                    msg.append(_("_{} more people..._").format(len(users) - 3))

        msg += [
            "",
            f"[{_('Click here to buy this item')}](https://t.me/{bot.username}?start=item-{self.id})",
        ]

        return "\n".join(msg)

    def generate_owner_message(self, context):
        _ = translator(context.lang)
        msg = [
            self.title,
            "",
            _("Published in *{}* chats").format(len(self.posts)),
            "",
            _("Starting Price: {}").format(
                format_currency(context, self.currency, self.base_price)
            ),
            "",
        ]
        if len(self.bids) == 0:
            msg.append(_("No one has made an offer"))
        elif len(self.bids) == 1:
            msg.append(
                _(
                    "Current Bid: {}".format(
                        format_currency(context, self.currency, self.bids[0]["price"])
                    )
                )
            )
        else:
            msg.append(
                _("Current Bid: {} with {} people in waiting list").format(
                    format_currency(context, self.currency, self.bids[0]["price"]),
                    len(self.bids) - 1,
                )
            )

        return "\n".join(msg)

    def chat_link(self, chat_id):
        post, _ = find_by(self.posts, "chat_id", chat_id)
        chat_id = int(str(chat_id)[4:])
        return f'[{self.title}](https://t.me/c/{chat_id}/{post["messages"][0]}'


def ignore_no_changes(f, **kwargs):
    try:
        f(**kwargs)
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise
        print("Warning: no changes!")
