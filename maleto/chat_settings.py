import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .utils import Callback, LANGUAGES, bot_handler, split_keyboard, translator
from .item import Item
from .user import User
from .chat import Chat

logger = logging.getLogger(__name__)


@bot_handler
def list_chats(update, context):
    _ = translator(context.lang)
    admin_chats = Chat.find(admins=context.user.id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    chat.title, callback_data=ChatSelectCallback.data(chat.id)
                )
            ]
            for chat in admin_chats
        ],
    )
    update.message.reply_text("Pick you shop", reply_markup=kb)


class ChatSelectCallback(Callback):
    name = "chatselect"

    def perform(self, context, query, chat_id):
        chat = Chat.find_by_id(chat_id)
        _ = translator(context.lang)
        msg = "\n".join([chat.title])
        btns = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Change Language", callback_data=ChatLangCallback.data(chat.id)
                    )
                ]
            ],
        )
        query.message.edit_text(text=msg, reply_markup=btns)
        query.answer()


class ChatLangCallback(Callback):
    name = "chatlang"

    def perform(self, context, query, chat_id, lang=None):
        chat = Chat.find_by_id(chat_id)
        _ = translator(context.lang)
        if lang is None:
            msg = "\n".join([chat.title, "", _("Select language")])
            l = [
                InlineKeyboardButton(n, callback_data=ChatLangCallback.data(chat.id, n))
                for n in LANGUAGES.keys()
            ]
            btns = InlineKeyboardMarkup(split_keyboard(l, 2))
            query.message.edit_text(text=msg, reply_markup=btns)
            query.answer()
        else:
            with chat:
                chat.lang = lang
            ChatSelectCallback().perform(context, query, chat_id)


@bot_handler
def cancel(update, context):
    return ConversationHandler.END


def handlers():
    yield CommandHandler("mystores", list_chats)
    yield from (ChatSelectCallback(), ChatLangCallback())