import logging

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler, ConversationHandler, Filters, MessageHandler

from maleto.core.bot import callback
from maleto.core.lang import LANGUAGES
from maleto.core.utils import split_keyboard
from maleto.user import User

logger = logging.getLogger(__name__)

LANG_SEL = range(1)


@callback
def lang_start(update, context):
    btns = ReplyKeyboardMarkup(
        split_keyboard([KeyboardButton(n) for n in LANGUAGES.keys()], 2)
    )
    update.message.reply_text("Select your language", reply_markup=btns)
    return LANG_SEL


@callback
def lang_select(update, context):
    lang = update.message.text
    if lang not in LANGUAGES.keys():
        update.message.reply_text(
            "Language not recognized",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        with User.find_by_id(update.effective_user.id) as user:
            user.lang = LANGUAGES[lang]
    update.message.reply_text(
        "Language changed",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


@callback
def cancel(update, context):
    return ConversationHandler.END


def handlers():
    canceler = MessageHandler(Filters.regex(r"/?[cC]ancel"), cancel)
    yield ConversationHandler(
        entry_points=[CommandHandler("changelang", lang_start)],
        states={
            LANG_SEL: [canceler, MessageHandler(Filters.text, lang_select)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
