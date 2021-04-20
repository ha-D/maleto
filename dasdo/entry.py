from telegram.ext import CommandHandler, Filters

from .item import Item


def on_start(update, context):
    if len(context.args) == 0 or context.args[0] == "":
        return

    action, arg = context.args[0].split("-")
    if action == "item":
        return item_start(update, context, arg)


def item_start(update, context, item_id):
    user = update.message.from_user
    with Item.find_by_id(item_id) as item:
        item.save_to_context(context)
        if item.owner_id == user.id:
            item.new_settings_message(context, publish=True)
        else:
            item.new_bid_message(context, user.id, publish=True)


def handlers():
    yield CommandHandler("start", on_start, Filters.text)