import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .utils import LANGUAGES, bot_handler
from .item import Item
from .user import User

logger = logging.getLogger(__name__)

LANG_SEL = range(1)


@bot_handler
def lang_start(update, context):
    btns = ReplyKeyboardMarkup([KeyboardButton(n) for n in LANGUAGES.keys()], 2)
    update.message.reply_text(
        "Select your language", parse_mode=ParseMode.MARKDOWN, reply_markup=btns
    )
    return LANG_SEL


@bot_handler
def lang_select(update, context):
    lang = update.message.text
    if lang not in LANGUAGES.keys():
        update.message.reply_text(
            "Language not recognized",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        with User.find_by_id(update.effective_user.id) as user:
            user.lang = LANGUAGES[lang]
    update.message.reply_text(
        "Language changed",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


@bot_handler
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
        # run_async=True # Run sync break multiple images
    )
