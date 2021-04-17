import logging
from telegram.error import BadRequest
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers

from .item import Item
from .utils import Callback, find_best_inc, bot_handler, find_by, translator

logger = logging.getLogger(__name__)

OPTIONS, OFFER = range(2)


def publish_bid_message(context, item, user_id, message_id=None):
    if message_id is None:
        message_id = item.get_bid_message(user_id)

    if message_id is None:
        return

    bid, pos = find_by(item.bids, "user_id", user_id)
    if pos == 0:
        msg, btns = buyer(context, item, bid)
    elif pos > 0:
        msg, btns = in_waiting_list(context, item, bid, pos)
    elif len(item.bids) == 0:
        msg, btns = no_bidder(context, item)
    else:
        msg, btns = not_bidding(context, item)

    try:
        context.bot.edit_message_caption(
            chat_id=user_id,
            message_id=message_id,
            caption=msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=btns,
        )
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise


def buyer(context, item, bid):
    _ = translator(context.lang)
    msg = _("You are the current buyer with {}").format(bid["price"])
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("I don't want it anymore"),
                    callback_data=RevokeBidCallback.data(item.id),
                )
            ]
        ]
    )
    return msg, btns


def in_waiting_list(context, item, bid, pos):
    _ = translator(context.lang)
    msg = _("You have bidded {} and are currently {} in the waiting list").format(
        bid["price"], pos
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Make Higher Offer"), callback_data=BidCallback.data(item.id)
                ),
                InlineKeyboardButton(
                    _("I don't want it anymore"),
                    callback_data=RevokeBidCallback.data(item.id),
                ),
            ],
        ]
    )
    return msg, btns


def no_bidder(context, item):
    _ = translator(context.lang)
    msg = _("No ones buying, the price is {} you want it?").format(item.base_price)
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Buy with this price"),
                    callback_data=WaitListCallback.data(item.id, item.base_price),
                ),
                InlineKeyboardButton(
                    _("Make Higher Offer"), callback_data=BidCallback.data(item.id)
                ),
            ],
        ]
    )
    return msg, btns


def not_bidding(context, item):
    highest_bid = max(item.bids, key=lambda b: b["price"])["price"]
    _ = translator(context.lang)
    msg = _("The highest bid is {}, do you want to make an offer?").format(highest_bid)
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Go in queue with this price"),
                    callback_data=WaitListCallback.data(item.id, highest_bid),
                ),
                InlineKeyboardButton(
                    _("Make Higher Offer"), callback_data=BidCallback.data(item.id)
                ),
            ],
        ]
    )
    return msg, btns


class RevokeBidCallback(Callback):
    name = "revoke"

    def perform(self, context, query, item_id):
        user = query.from_user
        _ = translator(context.lang)
        with Item.find_by_id(item_id) as item:
            item.publish_bid_message(context, user.id)
            item.remove_user_bid(context, user.id)
            item.publish(context)
            query.answer(_("Offer removed"))


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
                item.add_user_bid(context, user.id, price)
                item.publish(context)
                query.answer()
            except ValueError as e:
                item.publish_bid_message(context, user.id)
                query.answer(e.message)


def ask_for_bid(context, message, item, error=None):
    item.save_to_context(context)
    highest_bid = max(item.bids, key=lambda b: b["price"])["price"]

    min_price_inc = item.min_price_inc or find_best_inc(item.base_price)
    prices = [highest_bid + min_price_inc * i for i in range(3)]
    _ = translator(context.lang)
    msg = _("Enter your offer")
    if error is not None:
        msg = f"{error}\n{msg}"
    message.reply_markdown(
        text=msg,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(str(p)) for p in prices]]),
    )


@bot_handler
def on_bid(update, context):
    with Item.from_context(context) as item:
        _ = translator(context.lang)
        price = int(update.message.text)
        user = update.message.from_user
        try:
            item.add_user_bid(context, user.id, price)
            update.message.reply_text(
                _("Thanks you have it"), reply_markup=ReplyKeyboardRemove()
            )
            item.clear_context(context)
            item.publish(context)
            return ConversationHandler.END
        except ValueError as e:
            update.message.reply_text(
                _("Could not do it:"), reply_markup=ReplyKeyboardRemove()
            )
            ask_for_bid(context, update.message, item, _("Could not do it sorry"))
            return OFFER


@bot_handler
def cancel(update, context):
    _ = translator(context.lang)
    Item.C(context, remove=True)
    update.message.reply_text(
        _("Ok cool, nothing happened"), reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def handlers():
    yield ConversationHandler(
        entry_points=[RevokeBidCallback(), BidCallback(), WaitListCallback()],
        states={OFFER: [MessageHandler(Filters.text, on_bid)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
