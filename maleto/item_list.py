import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler

from maleto.core.bot import InlineButtonCallback, callback, inline_button_callback
from maleto.core.lang import _
from maleto.item import Item

logger = logging.getLogger(__name__)


@callback
def list_items(update, context):
    Item.clear_context(context)
    items = Item.find(owner_id=context.user.id)
    if len(items) == 0:
        message = _(
            "You don't have any items. Use the `/newitem` command to create one."
        )
        update.message.reply_text(text=message)
    else:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        s.title,
                        callback_data=select_item_callback.data(s.id),
                    ),
                ]
                for s in items
            ]
        )
        message = "\n".join(
            [
                _("Click on one any item to view more options"),
            ]
        )
        update.message.reply_text(text=message, reply_markup=kb)


@inline_button_callback("selectitem")
def select_item_callback(update, context, item_id):
    item = Item.find_by_id(item_id)
    update.callback_query.edit_message_reply_markup(InlineKeyboardMarkup([]))
    with item:
        item.new_settings_message(context, publish=True)
    update.callback_query.answer()


def handlers():
    yield from (
        CommandHandler("myitems", list_items),
        InlineButtonCallback(select_item_callback),
    )
