import logging
from re import A
from telegram.error import BadRequest

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .item import Item
from .user import User
from .utils import Callback
from .item_bid import RevokeBidCallback, BidCallback, WaitListCallback

logger = logging.getLogger(__name__)


def publish_interaction_message(context, item, user_id, imes=None):
    if imes is None:
        imes = item.get_interaction_message(user_id)

    _, pos_in_queue, total_queue_size = item.get_latest_bids(user_id)
    if user_id == item.owner_id:
        msg, btns = imes_owner(imes, item, user_id)
    elif pos_in_queue == 0:
        msg, btns = imes_buyer(imes, item, user_id)
    elif pos_in_queue > 0:
        msg, btns = imes_in_waiting_list(imes, item, user_id)
    elif total_queue_size == 0:
        msg, btns = imes_no_bidders(imes, item, user_id)
    else:
        msg, btns = imes_not_bidding(imes, item, user_id)

    try:
        context.bot.edit_message_caption(
            chat_id=user_id,
            message_id=imes["message_id"],
            caption=msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=btns,
        )
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise


def imes_owner(imes, item, user_id):
    state = imes.get("state", "default")
    return {
        "default": imes_owner_default,
        "publishing": imes_owner_publishing,
        "deleting": imes_owner_deleting,
    }[state](item, user_id)


def imes_owner_default(item, user_id):
    n = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Publish", callback_data=PublishCallback.data(item.id)
                )
            ],
            [
                InlineKeyboardButton(
                    "🗑  Delete", callback_data=DeleteCallback.data(item.id)
                ),
                InlineKeyboardButton(
                    "✏️  Edit", callback_data=EditCallback.data(item.id)
                ),
            ],
        ]
    )
    return item.generate_owner_message(), n


def imes_owner_publishing(item, user_id):
    user = User.find_by_id(user_id)
    existing = set([s["chat_id"] for s in item.posts])
    buttons = [
        InlineKeyboardButton(
            "◀️ Back", callback_data=PublishCallback.data(item.id, "cancel")
        )
    ]
    chat_names = Chat.get_chat_names(user.chats)
    for chat_id in user.chats:
        if chat_id in existing:
            action = "rem"
            btn_msg = f"Remove from {chat_names.get(chat_id)}"
        else:
            action = "add"
            btn_msg = f"Publish to {chat_names.get(chat_id)}"
        buttons.append(
            InlineKeyboardButton(
                btn_msg, callback_data=PublishCallback.data(item.id, action, chat_id)
            )
        )
    return item.generate_owner_message(), InlineKeyboardMarkup([[b] for b in buttons])


def imes_owner_deleting(item, user_id):
    msg = "\n".join(
        [item.get_owner_message(), "Are you sure you want to delete this item? 🙀"]
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Yes", callback_data=DeleteCallback.data(item.id, "yes")
                ),
                InlineKeyboardButton(
                    "No", callback_data=DeleteCallback.data(item.id, "no")
                ),
            ]
        ]
    )
    return msg, btns


def imes_buyer(imes, item, user_id):
    price, _, _ = item.get_latest_bids(user_id)
    msg = (f"You are the current buyer with {price}",)
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "I don't want it anymore",
                    callback_data=RevokeBidCallback.data(item.id),
                )
            ]
        ]
    )
    return msg, btns


def imes_in_waiting_list(imes, item, user_id):
    price, pos_in_queue, _ = item.get_latest_bids(user_id)
    msg = f"You are {pos_in_queue}th person in queue for price {price}"
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Make Higher Offer", callback_data=BidCallback.data(item.id)
                ),
                InlineKeyboardButton(
                    "I don't want it anymore",
                    callback_data=RevokeBidCallback.data(item.id),
                ),
            ],
        ]
    )
    return msg, btns


def imes_no_bidders(imes, item, user_id):
    price, _, _ = item.get_latest_bids(user_id)
    msg = f"No ones buying, the price is {price} you want it?"
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Buy with this price",
                    callback_data=WaitListCallback.data(item.id, price),
                ),
                InlineKeyboardButton(
                    "Make Higher Offer", callback_data=BidCallback.data(item.id)
                ),
            ],
        ]
    )
    return msg, btns


def imes_not_bidding(imes, item, user_id):
    price, _, total_queue_size = item.get_latest_bids(user_id)
    msg = f"There are {total_queue_size} people buying with price {price}, you want it"
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Go in queue with this price",
                    callback_data=WaitListCallback.data(item.id, price),
                ),
                InlineKeyboardButton(
                    "Make Higher Offer", callback_data=BidCallback.data(item.id)
                ),
            ],
        ]
    )
    return msg, btns


class DeleteCallback(Callback):
    name = "delete"

    def perform(self, context, query, item_id, action=""):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            if action == "":
                item.change_interaction_message_state(user.id, "deleting")
                publish_interaction_message(context, item, user.id)
                query.answer()
            elif action == "yes":
                item.delete_all_messages(context, user.id)
                item.delete()
                query.answer("Item deleted")
            elif action == "no":
                item.change_interaction_message_state(user.id, "default")
                publish_interaction_message(context, item, user.id)
                query.answer()


class EditCallback(Callback):
    name = "edit"

    def perform(self, context, query, item_id, action=""):
        context.bot.send_message(
            chat_id=query.message.chat.id, text="Editing is not available yet, sorry"
        )
        query.answer()


class PublishCallback(Callback):
    name = "publish"

    def perform(self, context, query, item_id, action="", chat_id=None):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            if action == "":
                item.change_interaction_message_state(user.id, "publishing")
            elif action == "cancel":
                item.change_interaction_message_state(user.id, "default")
            elif action == "add":
                item.add_sale_message(context, chat_id)
            elif action == "rem":
                item.remove_sale_message(context, chat_id)
            publish_interaction_message(context, item, user.id)
            query.answer()


def handlers():
    yield from (DeleteCallback(), EditCallback(), PublishCallback())
