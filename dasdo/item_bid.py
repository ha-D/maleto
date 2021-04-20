import logging
from telegram.error import BadRequest
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers

from .item import Item
from .utils.currency import format_currency
from .utils import (
    Callback,
    find_best_inc,
    bot_handler,
    find_by,
    split_keyboard,
    translator,
)

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
                    _("Remove Offer"),
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
                    _("Change Offer"), callback_data=BidCallback.data(item.id)
                ),
                InlineKeyboardButton(
                    _("Remove Offer"),
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
                    _("Make Offer"), callback_data=BidCallback.data(item.id)
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
                    _("Make Offer"), callback_data=BidCallback.data(item.id)
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
        query.answer()
        return OFFER


def ask_for_bid(context, message, item, error=None):
    item.save_to_context(context)
    highest_bid = max(item.bids, key=lambda b: b["price"])["price"]

    _ = translator(context.lang)
    if error is not None:
        msg = "\n".join([error, "", _("Do you want to try again?")])
    else:
        msg = _("Enter your offer")

    min_price_inc = item.min_price_inc or find_best_inc(item.base_price)
    prices = [highest_bid + min_price_inc * i for i in range(4)]
    btns = split_keyboard(
        [KeyboardButton(str(p)) for p in prices] + [KeyboardButton("Cancel")], 2
    )
    message.reply_markdown(
        text=msg,
        reply_markup=ReplyKeyboardMarkup(btns),
    )


@bot_handler
def on_bid(update, context):
    with Item.from_context(context) as item:
        _ = translator(context.lang)
        price = int(update.message.text)
        user = update.message.from_user
        try:
            item.add_user_bid(context, user.id, price)
            if item.bids[0]["user_id"] == context.user.id:
                update.message.reply_text(
                    _("Congrats 🎉, you're the current buyer at {}").format(
                        format_currency(context, item.currency, price)
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )
            else:
                __, pos = find_by(item.bids, "user_id", context.user.id)
                update.message.reply_text(
                    _(
                        "You've made an offer for {} and are #{} in the waiting list"
                    ).format(price, pos),
                    reply_markup=ReplyKeyboardRemove(),
                )
            item.clear_context(context)
            item.publish(context)
            return ConversationHandler.END
        except ValueError as e:
            ask_for_bid(context, update.message, item, e.message)
            return OFFER


@bot_handler
def cancel(update, context):
    _ = translator(context.lang)
    Item.C(context, remove=True)
    update.message.reply_text(
        _("Ok no problem, cancelled"), reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def handlers():
    yield ConversationHandler(
        entry_points=[RevokeBidCallback(), BidCallback()],
        states={OFFER: [MessageHandler(Filters.text, on_bid)]},
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler("Cancel", cancel)],
    )
