import logging

from telegram.ext import CommandHandler, Filters

from maleto.item import Item
from maleto.utils import bot_handler, parse_start_params, trace


logger = logging.getLogger(__name__)


@bot_handler
@trace
def on_start(update, context):
    if len(context.args) == 0 or context.args[0] == "":
        return

    kwargs = parse_start_params(context.args[0])
    action = kwargs.pop('action')

    if action == "item":
        return item_start(update, context, kwargs)


@trace
def item_start(update, context, kwargs):
    item_id = kwargs.get('item')
    if item_id is None:
        logger.error('Missing item arg in start message')
        return
    lang = kwargs.get('lang')
    user = update.message.from_user
    with Item.find_by_id(item_id) as item:
        item.save_to_context(context)
        if item.owner_id == user.id:
            item.new_settings_message(context, publish=True)
        else:
            item.new_bid_message(context, user.id, lang=lang, publish=True)


def handlers():
    yield CommandHandler("start", on_start, Filters.text)