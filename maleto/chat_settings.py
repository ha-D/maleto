import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler

from maleto.chat import Chat
from maleto.core.bot import InlineButtonCallback, callback, inline_button_callback
from maleto.core.lang import LANGUAGES, _
from maleto.core.utils import split_keyboard

logger = logging.getLogger(__name__)


@callback
def list_chats(update, context):
    admin_chats = Chat.find(admins=context.user.id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    chat.title, callback_data=on_chat_select.data(chat.id)
                )
            ]
            for chat in admin_chats
        ],
    )
    update.message.reply_text("Pick you shop", reply_markup=kb)


@inline_button_callback("chatselect")
def on_chat_select(update, context, chat_id):
    query = update.callback_query
    chat = Chat.find_by_id(chat_id)
    msg = "\n".join([chat.title])
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Change Language", callback_data=on_chat_select.data(chat.id)
                )
            ]
        ],
    )
    query.message.edit_text(text=msg, reply_markup=btns)
    query.answer()


@inline_button_callback("chatlang")
def on_chat_lang(update, context, chat_id, lang=None):
    query = update.callback_query
    chat = Chat.find_by_id(chat_id)
    if lang is None:
        msg = "\n".join([chat.title, "", _("Select language")])
        l = [
            InlineKeyboardButton(n, callback_data=on_chat_select.data(chat.id, n))
            for n in LANGUAGES.keys()
        ]
        btns = InlineKeyboardMarkup(split_keyboard(l, 2))
        query.message.edit_text(text=msg, reply_markup=btns)
        query.answer()
    else:
        with chat:
            chat.lang = lang
        on_chat_select(update, context)


@callback
def cancel(update, context):
    return ConversationHandler.END


def handlers():
    yield CommandHandler("mystores", list_chats)
    yield from (
        InlineButtonCallback(on_chat_select),
        InlineButtonCallback(on_chat_lang),
    )
