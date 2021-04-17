import logging

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .item import Item

logger = logging.getLogger(__name__)


def item_start(update, context, item_id):
    user = update.message.from_user
    with Item.find_by_id(item_id) as item:
        item.save_to_context(context)
        if item.owner_id == user.id:
            item.new_settings_message(context, publish=True)
        else:
            item.new_bid_message(context, user.id, publish=True)
