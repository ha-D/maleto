import logging
import warnings
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, Filters, MessageHandler

from maleto.core.bot import (
    InlineButtonCallback,
    callback,
    inline_button_callback,
    trace,
)
from maleto.core.currency import (
    currency_name,
    deformat_number,
    format_currency,
    format_number,
)
from maleto.core.lang import _, convert_number, uselang
from maleto.core.utils import find_best_inc, find_by, split_keyboard
from maleto.item import Item
from maleto.user import User

logger = logging.getLogger(__name__)

CUSTOM_OFFER = range(1)

STATE_DEFAULT, STATE_BID = range(2)
(
    ACTION_SUGGEST_BIDS,
    ACTION_SELECT_BID,
    ACTION_CUSTOM_BID,
    ACTION_REVOKE,
    ACTION_CANCEL,
) = range(5)


@trace
def publish_bid_message(context, item, user_id):
    bmes, __ = find_by(item.bid_messages, "user_id", user_id)
    if bmes is None:
        return
    message_id = bmes["message_id"]
    user = User.find_by_id(user_id)

    with uselang(user.lang or bmes.get("lang")):
        state = bmes.get("state", STATE_DEFAULT)
        if item.closed:
            msg = _("This item is no longer on sale")
            btns = InlineKeyboardMarkup([])
        if state == STATE_BID:
            msg, btns = show_bid_suggestions(item)
        else:
            bid, pos = find_by(item.bids, "user_id", user_id)
            if pos == 0:
                msg, btns = buyer(context, item, bid)
            elif pos > 0:
                msg, btns = in_waiting_list(context, item, bid, pos)
            elif len(item.bids) == 0:
                msg, btns = no_bidder(context, item)
            else:
                msg, btns = not_bidding(context, item)

    msg = "\n".join([f"*{item.title}*", "", msg])

    try:
        context.bot.edit_message_caption(
            chat_id=user_id,
            message_id=message_id,
            caption=msg,
            reply_markup=btns,
        )
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise


def buyer(context, item, bid):
    msg = _("You are the current buyer with {}").format(
        format_currency(item.currency, bid["price"])
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Remove Offer"),
                    callback_data=bid_callback.data(item.id, ACTION_REVOKE),
                )
            ]
        ]
    )
    return msg, btns


def in_waiting_list(context, item, bid, pos):
    msg = _("You have bidded {} and are currently {} in the waiting list").format(
        format_currency(item.currency, bid["price"]), convert_number(pos)
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Change Offer"),
                    callback_data=bid_callback.data(item.id, ACTION_SUGGEST_BIDS),
                ),
                InlineKeyboardButton(
                    _("Remove Offer"),
                    callback_data=bid_callback.data(item.id, ACTION_REVOKE),
                ),
            ],
        ]
    )
    return msg, btns


def no_bidder(context, item):
    msg = "\n".join(
        [
            _("There are no offers for this item"),
            _("Base Price: {}").format(format_currency(item.currency, item.base_price)),
            "",
            _("Would you like to place an offer?"),
            "",
        ]
    )

    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Make Offer"),
                    callback_data=bid_callback.data(item.id, ACTION_SUGGEST_BIDS),
                ),
            ],
        ]
    )
    return msg, btns


def not_bidding(context, item):
    highest_bid = max(item.bids, key=lambda b: b["price"])["price"]
    msg = _("The highest bid is {}, do you want to make an offer?").format(
        format_currency(item.currency, highest_bid)
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Make Offer"),
                    callback_data=bid_callback.data(item.id, ACTION_SUGGEST_BIDS),
                ),
            ],
        ]
    )
    return msg, btns


@inline_button_callback("bid")
def bid_callback(update, context, item_id, action=ACTION_SUGGEST_BIDS, price=None):
    Item.clear_context(context)
    with Item.find_by_id(item_id) as item:
        bmes, __ = find_by(item.bid_messages, "user_id", context.user.id)
        if bmes is None:
            logger.error(
                f"Missing bid_message in bid_callback",
                extra=dict(item=item.id, user=context.user.id),
            )
            item.new_bid_message(context, context.user.id, publish=True)
            update.callback_query.answer(_("Something went wrong please try again"))
            return None
        with uselang(context.user.lang or bmes.get("lang")):
            if action == ACTION_SUGGEST_BIDS:
                bmes["state"] = STATE_BID
                publish_bid_message(context, item, context.user.id)
            elif action == ACTION_SELECT_BID:
                on_bid(context, item, bmes, price)
            elif action == ACTION_CANCEL:
                bmes["state"] = STATE_DEFAULT
                publish_bid_message(context, item, context.user.id)
            elif action == ACTION_CUSTOM_BID:
                ask_for_bid(context, item)
            elif action == ACTION_REVOKE:
                item.publish_bid_message(context, context.user.id)
                item.remove_user_bid(context, context.user.id)
                item.publish(context)
    update.callback_query.answer()
    return CUSTOM_OFFER


@trace
def show_bid_suggestions(item):
    highest_bid = item.base_price
    if item.bids:
        highest_bid = max(item.bids, key=lambda b: b["price"])["price"]

    msg = _("Select your offer")

    min_price_inc = item.min_price_inc or find_best_inc(
        max(item.base_price, highest_bid)
    )
    prices = [max(item.base_price, highest_bid) + min_price_inc * i for i in range(4)]
    btns = split_keyboard(
        [
            InlineKeyboardButton(
                text=format_number(p),
                callback_data=bid_callback.data(item.id, ACTION_SELECT_BID, p),
            )
            for p in prices
        ]
        + [
            InlineKeyboardButton(
                text=_("Back"), callback_data=bid_callback.data(item.id, ACTION_CANCEL)
            ),
            InlineKeyboardButton(
                text=_("Custom Price"),
                callback_data=bid_callback.data(item.id, ACTION_CUSTOM_BID),
            ),
        ],
        2,
    )
    return msg, InlineKeyboardMarkup(btns)


@trace
def ask_for_bid(context, item, error=None):
    if error is not None:
        msg = "\n".join([error, "", _("Do you want to try again?")])
    else:
        msg = _("Enter your offer in {}").format(currency_name(item.currency))
    context.bot.send_message(chat_id=context.user.id, text=msg)
    item.save_to_context(context)


@callback
def on_custom_bid(update, context):
    # This is to handle the case where the user forgets to click on the Start button
    # before click on the bid button (from a previous bid_message)
    if update.message.text.startswith("/start"):
        return None

    try:
        item = Item.from_context(context)
    except Exception:
        logger.error("Empty context in on_custom_bid", extra=dict(user=context.user.id))
        update.message.reply_text(_("Something went wrong please try again"))
        return

    with item:
        bmes, __ = find_by(item.bid_messages, "user_id", context.user.id)
        if bmes is None:
            logger.error(
                f"Missing bid_message in `on_bid`",
                extra=dict(item=item.id, user=context.user.id),
            )
            update.message.reply_text(_("Something went wrong please try again"))
            item.new_bid_message(context, context.user.id, publish=True)
            return None
        with uselang(context.user.lang or bmes.get("lang")):
            on_bid(context, item, bmes, update.message.text)


@trace
def on_bid(context, item, bmes, price):
    try:
        price = deformat_number(price)
    except ValueError as e:
        ask_for_bid(
            context,
            item,
            _("That is not a valid price, please enter a number"),
        )
        return CUSTOM_OFFER

    try:
        item.add_user_bid(context, context.user.id, price)
        if item.bids[0]["user_id"] == context.user.id:
            if item.bids[0]["price"] >= item.base_price:
                msg = _("Congrats 🎉, you're the current buyer at {}")
            else:
                msg = _(
                    "You have placed the highest bid at {}. However, this is lower than the base price for this item."
                )
            context.bot.send_message(
                chat_id=context.user.id,
                text=msg.format(format_currency(item.currency, price)),
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            __, pos = find_by(item.bids, "user_id", context.user.id)
            context.bot.send_message(
                chat_id=context.user.id,
                text=_(
                    "You've made an offer for {} and are #{} in the waiting list"
                ).format(format_currency(item.currency, price), convert_number(pos)),
                reply_markup=ReplyKeyboardRemove(),
            )
        item.clear_context(context)
        item.publish(context)
        bmes["state"] = STATE_DEFAULT
        publish_bid_message(context, item, context.user.id)
        return ConversationHandler.END
    except ValueError as e:
        if len(e.args):
            err = e.args[0]
        else:
            err = _("Something went wrong please try again")
        ask_for_bid(context, item, err)
        return CUSTOM_OFFER


@callback
def cancel(update, context):
    Item.clear_context(context)
    update.message.reply_text(
        _("Ok no problem, cancelled"), reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


@callback
def abort(update, context):
    return ConversationHandler.END


def handlers():
    canceler = MessageHandler(Filters.regex(r"/?[cC]ancel"), cancel)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        yield ConversationHandler(
            entry_points=[InlineButtonCallback(bid_callback)],
            states={
                CUSTOM_OFFER: [
                    canceler,
                    MessageHandler(Filters.text, on_custom_bid),
                    InlineButtonCallback(bid_callback),
                ]
            },
            fallbacks=[canceler, MessageHandler(Filters.command, abort)],
            conversation_timeout=timedelta(minutes=5),
        )
