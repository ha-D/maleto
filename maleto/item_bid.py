import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers

from .item import Item
from .utils import Callback, find_best_inc, bot_handler

logger = logging.getLogger(__name__)

OPTIONS, OFFER = range(2)


class RevokeBidCallback(Callback):
    name = "revoke"

    def perform(self, context, query, item_id):
        user = query.from_user
        with Item.find_by_id(item_id) as item:
            item.publish_to_interaction_message_for_user(context, user.id)
            _, pos_in_queue, _ = item.get_latest_bids(user.id)
            if pos_in_queue < 0:
                query.answer("Not in queue")
            else:
                item.remove_user_from_bids(user.id)
                item.publish_to_messages(context)
                query.answer("Offer removed")


class BidCallback(Callback):
    name = "bid"

    def perform(self, context, query, item_id):
        with Item.find_by_id(item_id) as item:
            ask_for_bid(context, query.message, item)
            return OFFER


class WaitListCallback(Callback):
    name = "waitinglist"

    def perform(self, context, query, item_id, price):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            try:
                item.add_user_bid(user.id, price)
                item.publish_to_messages(context)
                query.answer("Done")
            except ValueError as e:
                item.publish_to_interaction_message_for_user(context, user.id)
                query.answer(e.message)


def ask_for_bid(context, message, item, error=None):
    item.save_to_context(context)
    price, _, _ = item.get_latest_bids()

    min_price_inc = item.min_price_inc or find_best_inc(item.base_price)
    prices = [price + min_price_inc * i for i in range(3)]
    msg = "Enter your offer"
    if error is not None:
        msg = f"{error}\n{msg}"
    message.reply_markdown(
        text=msg,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(str(p)) for p in prices]]),
    )


@bot_handler
def on_bid(update, context):
    with Item.from_context(context) as item:
        price = int(update.message.text)
        user = update.message.from_user
        try:
            item.add_user_bid(user.id, price)
            update.message.reply_text(
                "Thanks you have it", reply_markup=ReplyKeyboardRemove()
            )
            item.clear_context(context)
            item.publish_to_messages(context)
            return ConversationHandler.END
        except ValueError as e:
            update.message.reply_text(
                "Could not do it:", reply_markup=ReplyKeyboardRemove()
            )
            ask_for_bid(context, update.message, item, "Could not do it sorry")
            return OFFER


@bot_handler
def cancel(update, context):
    Item.C(context, remove=True)
    update.message.reply_text(
        "Ok cool, nothing happened", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def handlers():
    yield ConversationHandler(
        entry_points=[RevokeBidCallback(), BidCallback(), WaitListCallback()],
        states={OFFER: [MessageHandler(Filters.text, on_bid)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
