import logging
import random
import string
import time

from telegram import InlineKeyboardMarkup, InputMediaPhoto, ParseMode
from telegram.error import BadRequest
from telegram.files.inputfile import InputFile

from maleto.core import metrics
from maleto.core.bot import create_start_params, get_bot, trace
from maleto.core.currency import format_currency
from maleto.core.lang import _, convert_number, uselang
from maleto.core.media import minion_photo, open_media
from maleto.core.model import Model
from maleto.core.utils import find_best_inc, find_by

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
                "active": False,
                "photos": [],
                "bids": [],
                "posts": [],
                "stores": [],
                "bid_messages": [],
                **kwargs,
            }
        )

    def __str__(self):
        return f"Item [{self.id}] {self.title}"

    def __repr__(self):
        return str(self)

    @classmethod
    def new(cls, owner_id):
        item = Item()
        item.owner_id = owner_id
        item.id = "".join(random.choices(string.ascii_lowercase + string.digits, k=11))
        return item

    @classmethod
    def find(cls, **kwargs):
        return super().find(**{"active": True, **kwargs})

    @property
    def owner(self):
        from maleto.user import User

        return User.find_by_id(self.owner_id)

    def _remove_user_bid(self, context, user_id):
        self.bids = [b for b in self.bids if b["user_id"] != user_id]

    @trace
    def remove_user_bid(self, context, user_id, sort=True):
        self._remove_user_bid(context, user_id)
        if sort:
            self._sort_bids()
        logger.info("Bid removed", extra=dict(item=self.id, user=user_id))
        metrics.item_bid_remove.inc()

    @trace
    def add_user_bid(self, context, user_id, price, sort=True):
        # TODO: check min price inc

        if self.base_price and price < self.base_price:
            raise ValueError(_("Your offer is too low"))

        previous_winner = None
        if self.bids:
            previous_winner = self.bids[0]

        min_price_inc = self.min_price_inc or find_best_inc(self.base_price)
        highest_bid = self.base_price
        if self.bids:
            highest_bid = max(self.bids, key=lambda b: b["price"])["price"]
        if price > highest_bid and price - highest_bid < min_price_inc:
            raise ValueError(
                _(
                    "You need to increase by at least {} if you want to offer a higher price"
                ).format(format_currency(self.currency, min_price_inc))
            )

        self._remove_user_bid(context, user_id)

        src_chat = None
        if context.chat:
            src_chat = context.chat.id
        self.bids.append(
            {
                "user_id": user_id,
                "price": price,
                "ts": time.time(),
                "src_chat_id": src_chat,
            }
        )
        if sort:
            self._sort_bids()

        logger.info("New bid placed", extra=dict(item=self.id, user=user_id))
        metrics.item_bid_add.inc()

        self._handle_winner_change(context, previous_winner, self.bids[0])

    @trace
    def _sort_bids(self):
        self.bids = sorted(
            self.bids, key=lambda b: (b["price"], -b["ts"]), reverse=True
        )

    @trace
    def _handle_winner_change(self, context, prev_winner, new_winner):
        if (
            prev_winner is not None
            and new_winner is not None
            and prev_winner["user_id"] == new_winner["user_id"]
        ):
            return

        if prev_winner is not None and new_winner is not None:
            metrics.item_buyer_change.inc()

        if prev_winner is not None:
            logger.info(
                "Winning bidder changed",
                extra=dict(
                    item=self.id,
                    prev_winner=prev_winner["user_id"]
                    if prev_winner is not None
                    else "-",
                    new_winner=new_winner["user_id"] if new_winner is not None else "-",
                ),
            )
            link = f"*{self.title}*"
            # TODO: src_chat not working propertly, needs investigating
            # if src_chat := prev_winner.get("src_chat_id"):
            #     link = self.chat_link(src_chat)
            context.bot.send_message(
                chat_id=prev_winner["user_id"],
                text="\n".join(
                    [
                        _("🙀 You are no longer the winning bidder for this item:"),
                        "",
                        link,
                    ]
                ),
            )
        if new_winner is not None and context.user.id != new_winner["user_id"]:
            link = f"*{self.title}*"
            # if src_chat := new_winner.get("src_chat_id"):
            #     link = self.chat_link(src_chat)
            context.bot.send_message(
                chat_id=new_winner["user_id"],
                text="\n".join(
                    [
                        _("🥳 You are now the winning bidder for this item:"),
                        "",
                        link,
                    ]
                ),
            )

    @trace
    def add_to_chat(self, context, chat_id):
        from maleto.chat import Chat

        chat = Chat.find_by_id(chat_id)
        with chat:
            index = chat.next_index
            chat.next_index += 1

        post, _ = find_by(self.posts, "chat_id", chat_id)
        if not post:
            with uselang(chat.lang):
                media = [InputMediaPhoto(media=photo) for photo in self.photos]
                media[0].caption = self.generate_sale_message(context)
                media[0].parse_mode = ParseMode.MARKDOWN
                messages = context.bot.send_media_group(chat_id=chat_id, media=media)
                self.posts.append(
                    {
                        "chat_id": chat_id,
                        "messages": [m.message_id for m in messages],
                        "index": index,
                    }
                )
        # Need to save for the chat publish to work
        self.save()
        chat.publish_info_message(context)

    @trace
    def remove_from_chat(self, context, chat_id):
        from maleto.chat import Chat

        post, idx = find_by(self.posts, "chat_id", chat_id)
        if post:
            for message_id in post["messages"]:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            del self.posts[idx]
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    @trace
    def new_bid_message(
        self, context, user_id, message_id=None, lang=None, publish=True
    ):
        prev_mes, __ = find_by(self.bid_messages, "user_id", user_id)
        if prev_mes is not None:
            logger.debug(
                f"Clearing previous user bid message",
                extra=dict(user=user_id, msg_id=prev_mes["message_id"]),
            )
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

        if message_id is None:
            message = self.initiate_settings_or_bid_message(context, user_id)
            message_id = message.message_id
            logger.debug(
                f"New bid message created", extra=dict(user=user_id, msg_id=message_id)
            )
        if prev_mes:
            prev_mes["message_id"] = message_id
            prev_mes["lang"] = lang
        else:
            self.bid_messages.append(
                {"user_id": user_id, "message_id": message_id, "lang": lang}
            )
        if publish:
            self.publish_bid_message(context, user_id)

    @trace
    def new_settings_message(self, context, message_id=None, publish=True):
        prev_mes = self.settings_message
        if prev_mes is not None:
            # Clear previous settings message for this user
            try:
                context.bot.edit_message_caption(
                    chat_id=self.owner_id,
                    message_id=prev_mes["message_id"],
                    caption=f"{self.title}",
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                pass
        if message_id is None:
            message = self.initiate_settings_or_bid_message(context, self.owner.id)
            message_id = message.message_id
        self.settings_message = {"message_id": message_id, "state": "default"}
        if publish:
            self.publish_settings_message(context)

    def initiate_settings_or_bid_message(self, context, user_id):
        try:
            return context.bot.send_photo(
                chat_id=user_id, photo=self.photos[0], caption=_("Please wait...")
            )
        except BadRequest as e:
            # TODO: Sending photos with file_id seems to fail after a few days since the
            # last time the photo was used. Need to investigate further. For now we'll
            # fallback to sending the photo from the media dir or a minion photo if
            # that doesn't exist
            if "Wrong file" in e.message:
                logger.error("Unable to start message with item photo", exc_info=e)
                if photo_file := open_media(self.photos[0]):
                    with photo_file:
                        return context.bot.send_photo(
                            chat_id=user_id,
                            photo=InputFile(photo_file),
                            caption=_("Please wait..."),
                        )
                else:
                    return context.bot.send_photo(
                        chat_id=user_id,
                        photo=InputFile(minion_photo),
                        caption=_("Please wait..."),
                    )
            else:
                raise

    def update_settings_message_state(self, state):
        mes = self.settings_message
        mes["state"] = state

    @trace
    def publish(self, context):
        from maleto.chat import Chat

        for post in self.posts:
            chat_id = post["chat_id"]
            message_id = post["messages"][0]
            chat = Chat.find_by_id(chat_id)
            with uselang(chat.lang):
                sale_message = self.generate_sale_message(context)
            ignore_no_changes(
                context.bot.edit_message_caption,
                chat_id=int(chat_id),
                message_id=message_id,
                parse_mode=ParseMode.MARKDOWN,
                caption=sale_message,
            )

        self.publish_settings_message(context)

        for mes in self.bid_messages:
            self.publish_bid_message(context, mes["user_id"])

    def publish_settings_message(self, context):
        from maleto.item_settings import publish_settings_message

        return publish_settings_message(context, self)

    def publish_bid_message(self, context, user_id):
        from maleto.item_bid import publish_bid_message

        return publish_bid_message(context, self, user_id)

    @trace
    def delete_all_messages(self, context):
        from maleto.user import User

        for bmes in self.bid_messages:
            try:
                user = User.find_by_id(bmes["user_id"])
                if user is None:
                    continue
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
                    bmes["user_id"],
                    bmes["message_id"],
                    exc_info=True,
                )

        if smes := self.settings_message:
            try:
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

    @trace
    def generate_sale_message(self, context):
        from maleto.user import User

        bot = get_bot(context)

        current_price = self.base_price
        if len(self.bids) > 0:
            current_price = self.bids[0]["price"]

        from maleto.core.lang import current_lang

        clang = current_lang()

        msg = [
            f"*{self.title}*",
            "",
            _("Seller: {}").format(self.owner.link()),
            "",
            self.description,
            "",
        ]

        def bidline(bid):
            user = User.find_by_id(bid["user_id"])
            return "{}  {}".format(
                user.link(), format_currency(self.currency, bid["price"])
            )

        if len(self.bids) == 0:
            msg.append(
                _("Price: {}").format(format_currency(self.currency, current_price))
            )
        elif len(self.bids) > 0:
            msg += [_("Buyer: {}").format(bidline(self.bids[0])), ""]
            if len(self.bids) > 1:
                bids = self.bids[1:]
                msg.append(_("Waiting List:"))
                if len(bids) <= 4:
                    msg += [f"{bidline(b)}" for i, b in enumerate(bids)]
                elif len(bids) > 4:
                    msg += [f"{bidline(b)}" for i, b in enumerate(bids[:3])]
                    msg.append(_("_{} more people..._").format(len(bids) - 3))

        click_here = _("Click here to buy this item")

        params = {"action": "item", "item": self.id}
        if lang := current_lang():
            params["lang"] = lang
        msg += [
            "",
            f"[{click_here}](https://t.me/{bot.username}?start={create_start_params(**params)})",
            "",
        ]

        return "\n".join(msg)

    @trace
    def generate_owner_message(self, context):
        msg = [
            self.title,
            "",
            _("Published in *{}* chats").format(len(self.posts)),
            "",
            _("Starting Price: {}").format(
                format_currency(self.currency, self.base_price)
            ),
            "",
        ]
        if len(self.bids) == 0:
            msg.append(_("No one has made an offer"))
        elif len(self.bids) == 1:
            msg.append(
                _(
                    "Current Bid: {}".format(
                        format_currency(self.currency, self.bids[0]["price"])
                    )
                )
            )
        else:
            msg.append(
                _("Current Bid: {} with {} people in waiting list").format(
                    format_currency(self.currency, self.bids[0]["price"]),
                    len(self.bids) - 1,
                )
            )

        return "\n".join(msg)

    def chat_link(self, chat_id):
        post, _ = find_by(self.posts, "chat_id", chat_id)
        chat_id = int(str(chat_id)[4:])
        return f"{convert_number(post['index'])}. [{self.title}](https://t.me/c/{chat_id}/{post['messages'][0]})"


def ignore_no_changes(f, **kwargs):
    try:
        f(**kwargs)
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise
        print("Warning: no changes!")
