import logging
import string
import random

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.error import BadRequest

from .utils import find_by, get_bot
from .models import Model

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
            "published_messages",
            "bids",
            "base_price",
            "interaction_messages",
            "posts",
            "min_price_inc",
        )

    def __init__(self, **kwargs):
        super().__init__(
            **{
                "photos": [],
                "bids": [],
                "interaction_messages": [],
                "posts": [],
                "stores": [],
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

    def get_latest_bids(self, user_id=None):
        """
        Returns (price, place_in_queue, total_queue_size)
        """
        if len(self.bids) == 0:
            return self.base_price, -1, 0
        latest = self.bids[-1]
        price = latest["price"]
        bids = latest["users"]
        try:
            return price, bids.index(user_id), len(bids)
        except ValueError:
            return price, -1, len(bids)

    def remove_user_from_bids(self, user_id):
        for bid in self.bids:
            bid["users"] = [u for u in bid["users"] if u != user_id]
        self.bids = [b for b in self.bids if len(b["users"]) > 0]

    def add_user_bid(self, user_id, price):
        highest_price, place_in_queue, total_queue_size = self.get_latest_bids(user_id)
        if price < highest_price:
            raise ValueError("price low")
        if price == highest_price and place_in_queue >= 0:
            raise ValueError("already in queue")

        self.remove_user_from_bids(user_id)

        # if no bids or bidding with higher price
        if total_queue_size == 0 or highest_price < price:
            self.bids.append({"price": price, "users": [user_id]})
        else:
            self.bids[-1]["users"].append(user_id)

    def add_sale_message(self, context, chat_id):
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

    def remove_sale_message(self, context, chat_id):
        from .chat import Chat

        post, idx = find_by(self.posts, "chat_id", chat_id)
        if post:
            for message_id in post["messages"]:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            del self.posts[idx]
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    def publish_to_messages(self, context):
        from .item_interact import publish_interaction_message

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

        for imes in self.interaction_messages:
            publish_interaction_message(context, self, imes["user_id"], imes=imes)

    def change_user_interaction_message(self, context, user_id, message_id):
        imes, _ = find_by(self.interaction_messages, "user_id", user_id)
        if imes is not None:
            try:
                context.bot.edit_message_caption(
                    chat_id=imes["user_id"],
                    message_id=imes["message_id"],
                    caption=f"{self.title}",
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                pass
            imes["message_id"] = message_id
        else:
            self.interaction_messages.append(
                {"user_id": user_id, "message_id": message_id}
            )

    def change_interaction_message_state(self, user_id, state):
        imes, _ = find_by(self.interaction_messages, "user_id", user_id)
        imes["state"] = state

    def publish_to_interaction_message_for_user(self, context, user_id):
        from .item_interact import publish_interaction_message

        return publish_interaction_message(context, self, user_id)

    def get_interaction_message(self, user_id):
        imes, _ = find_by(self.interaction_messages, "user_id", user_id)
        return imes

    def delete_all_messages(self, context):
        for imes in self.interaction_messages:
            try:
                msg = "\n".join([self.title, "", "This item is no longer available"])
                context.bot.edit_message_caption(
                    chat_id=imes["user_id"],
                    message_id=imes["message_id"],
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest as e:
                logger.warning(
                    "Unable to disable interaction message (%d, %d)",
                    imes["chat_id"],
                    imes["message_id"],
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

        price, idx, q_len = self.get_latest_bids()
        msg = [
            f"*{self.title}*",
            f"Seller: {self.owner.link()}",
            "",
            self.description,
            "",
            f"Price: {price}",
        ]

        if q_len > 0:
            users = [User.find_by_id(uid) for uid in self.bids[-1]["users"]]
            msg += [f"Buyer: {users[0].link()}"]
            if len(users) > 1:
                users = users[1:]
                msg.append("Waiting List:")
                if len(users) <= 4:
                    msg += [f"{i+1}. {u.link()}" for i, u in enumerate(users)]
                elif len(users) > 4:
                    msg += [f"{i+1}. {u.link()}" for i, u in enumerate(users[:3])]
                    msg.append(f"_{len(users) - 3} more people..._")

        msg += [
            "",
            f"[Click here to buy this item](https://t.me/{bot.username}?start=item-{self.id})",
        ]

        return "\n".join(msg)

    def generate_owner_message(self):
        highest_price, _, total_queue_size = self.get_latest_bids()

        msg = [
            self.title,
            "",
            f"Published in *{len(self.posts)}* chats",
            "",
            f"Starting Price: {self.base_price}",
            "",
        ]
        if total_queue_size == 0:
            msg.append("No one has made an offer")
        elif total_queue_size == 1:
            f"Current Bid: {highest_price}",
        else:
            f"Current Bid: {highest_price} with {total_queue_size - 1} people in waiting list",

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
