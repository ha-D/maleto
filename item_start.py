import logging

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from item import Item

logger = logging.getLogger(__name__)


def item_start(update, context, item_id):
    user = update.message.from_user
    with Item.find_by_id(item_id) as item:
        item.save_to_context(context)
        msg = update.message.reply_photo(item.photos[0], caption='Please wait...')
        item.change_user_interaction_message(context, user.id, msg.message_id)
        item.publish_to_interaction_message_for_user(context, user.id)
