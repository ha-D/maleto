from gettext import translation
import logging
from re import A
from telegram.error import BadRequest

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .item import Item
from .user import User
from .utils import Callback, translator
from .chat import Chat

logger = logging.getLogger(__name__)


def publish_settings_message(context, item):
    smes = item.settings_message
    if smes is None:
        return

    state = smes.get("state", "default")
    msg, btns = {
        "default": settings_menu,
        "publishing": settings_publishing,
        "deleting": settings_deleting,
    }[state](context, item)

    try:
        context.bot.edit_message_caption(
            chat_id=item.owner_id,
            message_id=smes["message_id"],
            caption=msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=btns,
        )
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise


def settings_menu(context, item):
    btns = InlineKeyboardMarkup(
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
    return item.generate_owner_message(context), btns


def settings_publishing(context, item):
    _ = translator(context.lang) 
    user = item.owner
    existing = set([s["chat_id"] for s in item.posts])
    buttons = [
        InlineKeyboardButton(
            _("◀️ Back"), callback_data=PublishCallback.data(item.id, "cancel")
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
    return item.generate_owner_message(context), InlineKeyboardMarkup(
        [[b] for b in buttons]
    )


class PublishCallback(Callback):
    name = "publish"

    def perform(self, context, query, item_id, action="", chat_id=None):
        with Item.find_by_id(item_id) as item:
            if action == "":
                item.update_settings_message_state("publishing")
            elif action == "cancel":
                item.update_settings_message_state("default")
            elif action == "add":
                item.add_to_chat(context, chat_id)
            elif action == "rem":
                item.remove_from_chat(context, chat_id)
            publish_settings_message(context, item)
            query.answer()


def settings_deleting(context, item):
    _ = translator(context.lang) 
    msg = "\n".join(
        [
            item.generate_owner_message(context),
            _("Are you sure you want to delete this item? 🙀"),
        ]
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Yes"), callback_data=DeleteCallback.data(item.id, "yes")
                ),
                InlineKeyboardButton(
                    _("No"), callback_data=DeleteCallback.data(item.id, "no")
                ),
            ]
        ]
    )
    return msg, btns


class DeleteCallback(Callback):
    name = "delete"

    def perform(self, context, query, item_id, action=""):
        _ = translator(context.lang) 
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            if action == "":
                item.update_settings_message_state("deleting")
                publish_settings_message(context, item)
                query.answer()
            elif action == "yes":
                item.delete_all_messages(context, user.id)
                item.delete()
                query.answer(_("Item deleted"))
            elif action == "no":
                item.update_settings_message_state("default")
                publish_settings_message(context, item)
                query.answer()


class EditCallback(Callback):
    name = "edit"

    def perform(self, context, query, item_id, action=""):
        context.bot.send_message(
            chat_id=query.message.chat.id, text="Editing is not available yet, sorry"
        )
        query.answer()


def handlers():
    yield from (DeleteCallback(), EditCallback(), PublishCallback())
