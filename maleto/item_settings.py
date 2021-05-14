import logging
from datetime import timedelta
from re import A

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, Filters, MessageHandler

from maleto.chat import Chat
from maleto.core.bot import (
    InlineButtonCallback,
    callback,
    inline_button_callback,
    trace,
)
from maleto.core.currency import get_currencies
from maleto.core.lang import _
from maleto.core.utils import split_keyboard
from maleto.item import Item
from maleto.item_bid import ACTION_CANCEL
from maleto.user import User

logger = logging.getLogger(__name__)

(
    STATE_DEFAULT,
    STATE_PUBLISH,
    STATE_DELETE,
    STATE_CLOSE,
    STATE_CLOSE_NOTIF,
    STATE_EDIT,
) = range(6)
(
    ACTION_PUBLISH_CANCEL,
    ACTION_PUBLISH_ADD,
    ACTION_PUBLISH_REMOVE,
    ACTION_DELETE_YES,
    ACTION_DELETE_NO,
    ACTION_CLOSE_CANCEL,
    ACTION_CLOSE_NOW,
    ACTION_CLOSE_NOTIF,
    ACTION_EDIT_CANCEL,
    ACTION_EDIT_TITLE,
    ACTION_EDIT_DESCRIPTION,
    ACTION_EDIT_CURRENCY,
    ACTION_EDIT_PRICE,
    ACTION_EDIT_MIN_INC,
    ACTION_EDIT_LINK,
) = range(15)


(
    CONV_EDIT_TITLE,
    CONV_EDIT_DESCRIPTION,
    CONV_EDIT_CURRENCY,
    CONV_EDIT_PRICE,
    CONV_EDIT_MIN_INC,
    CONV_EDIT_LINK,
) = range(6)

cancel_markup = ReplyKeyboardMarkup([[KeyboardButton("Cancel")]])


@trace
def publish_settings_message(context, item):
    smes = item.settings_message
    if smes is None:
        return

    state = smes.get("state", STATE_DEFAULT)
    # REMOVEME: temporary fix
    if type(state) is not int:
        state = STATE_DEFAULT
    msg, btns = {
        STATE_DEFAULT: settings_menu,
        STATE_PUBLISH: settings_publishing,
        STATE_DELETE: settings_deleting,
        STATE_CLOSE: settings_closing,
        STATE_CLOSE_NOTIF: settings_closing_notif,
        STATE_EDIT: settings_editing,
    }[state](context, item)

    try:
        context.bot.edit_message_caption(
            chat_id=item.owner_id,
            message_id=smes["message_id"],
            caption=msg,
            reply_markup=btns,
        )
    except BadRequest as e:
        if "is not modified" not in e.message:
            raise


def settings_menu(context, item):
    if item.closed:
        open_or_close = InlineKeyboardButton(
            "🚪  Open", callback_data=item_open_callback.data(item.id)
        )
    else:
        open_or_close = InlineKeyboardButton(
            "🚪  Close", callback_data=item_close_callback.data(item.id)
        )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Publish", callback_data=item_publish_callback.data(item.id)
                )
            ],
            [
                open_or_close,
                InlineKeyboardButton(
                    "🗑  Delete", callback_data=item_delete_callback.data(item.id)
                ),
            ],
            [
                InlineKeyboardButton(
                    "✏️  Edit", callback_data=item_edit_callback.data(item.id)
                ),
            ],
        ]
    )
    return item.generate_owner_message(context), btns


def settings_publishing(context, item):
    user = item.owner
    existing = set([s["chat_id"] for s in item.posts])
    buttons = [
        InlineKeyboardButton(
            _("◀️ Back"), callback_data=item_publish_callback.data(item.id, "cancel")
        )
    ]
    chat_names = Chat.get_chat_names(user.chats)
    for chat_id in user.chats:
        if chat_id in existing:
            action = ACTION_PUBLISH_REMOVE
            btn_msg = f"Remove from {chat_names.get(chat_id)}"
        else:
            action = ACTION_PUBLISH_ADD
            btn_msg = f"Publish to {chat_names.get(chat_id)}"
        buttons.append(
            InlineKeyboardButton(
                btn_msg,
                callback_data=item_publish_callback.data(item.id, action, chat_id),
            )
        )
    return item.generate_owner_message(context), InlineKeyboardMarkup(
        [[b] for b in buttons]
    )


@inline_button_callback("publishitem")
def item_publish_callback(update, context, item_id, action=None, chat_id=None):
    with Item.find_by_id(item_id) as item:
        if action is None:
            item.update_settings_message_state(STATE_PUBLISH)
        elif action == ACTION_PUBLISH_CANCEL:
            item.update_settings_message_state(STATE_DEFAULT)
        elif action == ACTION_PUBLISH_ADD:
            item.add_to_chat(context, chat_id)
        elif action == ACTION_PUBLISH_REMOVE:
            item.remove_from_chat(context, chat_id)
        else:
            logger.error(
                "Invalid action received for 'item_publish_callback'",
                extra=dict(action=action, user=context.user.id, item=item.id),
            )
            Item.clear_context(context)
            item.update_settings_message_state(STATE_DEFAULT)
        publish_settings_message(context, item)
        update.callback_query.answer()


def settings_deleting(context, item):
    msg = "\n".join(
        [
            item.generate_owner_message(context),
            _("Are you sure you want to delete this item? 🙀"),
        ]
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("Yes"),
                    callback_data=item_delete_callback.data(item.id, ACTION_DELETE_YES),
                ),
                InlineKeyboardButton(
                    _("No"),
                    callback_data=item_delete_callback.data(item.id, ACTION_DELETE_NO),
                ),
            ]
        ]
    )
    return msg, btns


@inline_button_callback("deleteitem")
def item_delete_callback(update, context, item_id, action=None):
    query = update.callback_query
    with Item.find_by_id(item_id) as item:
        user = query.from_user
        if action is None:
            item.update_settings_message_state(STATE_DELETE)
            publish_settings_message(context, item)
            query.answer()
        elif action == ACTION_DELETE_YES:
            item.delete_all_messages(context)
            item.delete()
            query.answer(_("Item deleted"))
        elif action == ACTION_DELETE_NO:
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()
        else:
            logger.error(
                "Invalid action received for 'item_delete_callback'",
                extra=dict(action=action, user=context.user.id, item=item.id),
            )
            Item.clear_context(context)
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()


def settings_closing(context, item):
    msg = "\n".join(
        [
            item.generate_owner_message(context),
        ]
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("◀️ Back"),
                    callback_data=item_close_callback.data(
                        item.id, ACTION_CLOSE_CANCEL
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    _("Close Now"),
                    callback_data=item_close_callback.data(item.id, ACTION_CLOSE_NOW),
                ),
            ],
            [
                InlineKeyboardButton(
                    _("Send Closing Notification"),
                    callback_data=item_close_callback.data(item.id, ACTION_CLOSE_NOTIF),
                ),
            ],
        ]
    )
    return msg, btns


def settings_closing_notif(context, item):
    msg = "\n".join(
        [
            item.generate_owner_message(context),
            "",
            _(
                "This will send a message to users interested in this item to let them know the item will be closed soon"
            ),
            _("How long until you will close this item?"),
        ]
    )
    times = (
        (_("1 Minute"), 1),
        (_("5 Minutes"), 5),
        (_("10 Minutes"), 10),
        (_("30 Minutes"), 30),
        (_("1 Hour"), 60),
        (_("3 Hours"), 3 * 60),
        (_("6 Hours"), 6 * 60),
        (_("12 Hours"), 12 * 60),
        (_("24 Hours"), 24 * 60),
        (_("48 Hours"), 48 * 60),
    )
    btns = split_keyboard(
        [
            InlineKeyboardButton(
                t[0],
                callback_data=item_close_callback.data(
                    item.id, ACTION_CLOSE_NOTIF, t[1]
                ),
            )
            for t in times
        ],
        2,
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("◀️ Back"),
                    callback_data=item_close_callback.data(item.id, ACTION_CANCEL),
                ),
            ],
            *btns,
        ]
    )
    return msg, btns


@inline_button_callback("closeitem")
def item_close_callback(update, context, item_id, action=None, close_time=None):
    query = update.callback_query
    publish = False
    with Item.find_by_id(item_id) as item:
        if action is None:
            item.update_settings_message_state(STATE_CLOSE)
            publish_settings_message(context, item)
            query.answer()
        elif action == ACTION_CLOSE_CANCEL:
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()
        elif action == ACTION_CLOSE_NOW:
            item.closed = True
            publish = True
            query.answer(_("Item closed"))
        elif action == ACTION_CLOSE_NOTIF:
            if close_time is None:
                item.update_settings_message_state(STATE_CLOSE_NOTIF)
                publish_settings_message(context, item)
                query.answer()
            else:
                item.closing = True
                item.send_closing_notification(context, close_time)
                item.update_settings_message_state(STATE_DEFAULT)
                publish = True
                query.answer("Notification sent")
        else:
            logger.error(
                "Invalid action received for 'item_close_callback'",
                extra=dict(action=action, user=context.user.id, item=item.id),
            )
            Item.clear_context(context)
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()
    if publish:
        item.publish(context)
        for chat in item.get_all_chats():
            chat.publish_info_message(context)


@inline_button_callback("openitem")
def item_open_callback(update, context, item_id):
    query = update.callback_query
    with Item.find_by_id(item_id) as item:
        item.closed = False
        item.closing = False
        query.answer(_("Item closed"))
    item.publish(context)
    for chat in item.get_all_chats():
        chat.publish_info_message(context)


def settings_editing(context, item):
    msg = "\n".join(
        [
            item.generate_owner_message(context),
        ]
    )
    btns = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("◀️ Back"),
                    callback_data=item_edit_callback.data(item.id, ACTION_EDIT_CANCEL),
                ),
            ],
            [
                InlineKeyboardButton(
                    _("Title"),
                    callback_data=item_edit_callback.data(item.id, ACTION_EDIT_TITLE),
                ),
                InlineKeyboardButton(
                    _("Description"),
                    callback_data=item_edit_callback.data(
                        item.id, ACTION_EDIT_DESCRIPTION
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    _("Price"),
                    callback_data=item_edit_callback.data(item.id, ACTION_EDIT_PRICE),
                ),
                InlineKeyboardButton(
                    _("Currency"),
                    callback_data=item_edit_callback.data(
                        item.id, ACTION_EDIT_CURRENCY
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    _("Minimum Price Increase"),
                    callback_data=item_edit_callback.data(item.id, ACTION_EDIT_MIN_INC),
                ),
                InlineKeyboardButton(
                    _("Link"),
                    callback_data=item_edit_callback.data(item.id, ACTION_EDIT_LINK),
                ),
            ],
        ]
    )
    return msg, btns


@inline_button_callback("edititem")
def item_edit_callback(update, context, item_id, action=None):
    query = update.callback_query
    with Item.find_by_id(item_id) as item:
        if action is None:
            item.update_settings_message_state(STATE_EDIT)
            publish_settings_message(context, item)
            query.answer()
        elif action == ACTION_EDIT_CANCEL:
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()
        elif action == ACTION_EDIT_TITLE:
            item.save_to_context(context)
            query.message.reply_text(_("Enter the new title"))
            query.answer()
            return CONV_EDIT_TITLE
        elif action == ACTION_EDIT_DESCRIPTION:
            item.save_to_context(context)
            query.message.reply_text(_("Enter the new description"))
            query.answer()
            return CONV_EDIT_DESCRIPTION
        elif action == ACTION_EDIT_CURRENCY:
            item.save_to_context(context)
            currencies = get_currencies()
            btns = split_keyboard([KeyboardButton(text=c) for c in currencies], 2)
            query.message.reply_text(
                _("Select the new currency"), reply_markup=ReplyKeyboardMarkup(btns)
            )
            query.answer()
            return CONV_EDIT_CURRENCY
        elif action == ACTION_EDIT_PRICE:
            item.save_to_context(context)
            query.message.reply_text(_("Enter the new price"))
            query.answer()
            return CONV_EDIT_PRICE
        elif action == ACTION_EDIT_LINK:
            item.save_to_context(context)
            query.message.reply_text(_("Enter the new link"))
            query.answer()
            return CONV_EDIT_LINK
        elif action == ACTION_EDIT_MIN_INC:
            item.save_to_context(context)
            query.message.reply_text(_("Enter minimum price increase"))
            query.answer()
            return CONV_EDIT_MIN_INC
        else:
            logger.error(
                "Invalid action received for 'item_edit_callback'",
                extra=dict(action=action, user=context.user.id, item=item.id),
            )
            Item.clear_context(context)
            item.update_settings_message_state(STATE_DEFAULT)
            publish_settings_message(context, item)
            query.answer()


@callback
def on_edit_title(update, context):
    new_title = update.message.text
    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    with item:
        item.title = new_title
    item.publish(context)
    update.message.reply_text(_("Title updated"))
    return ConversationHandler.END


@callback
def on_edit_description(update, context):
    new_description = update.message.text
    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    with item:
        item.description = new_description
    item.publish(context)
    update.message.reply_text(_("Description updated"))
    return ConversationHandler.END


@callback
def on_edit_currency(update, context):
    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    currency_key = get_currencies().get(update.message.text)
    if currency_key is None:
        update.message.reply_text(
            _("I'm not familiar with that currency, please try again")
        )
        return CONV_EDIT_CURRENCY

    with item:
        item.currency = currency_key
    item.publish(context)
    update.message.reply_text(_("Currency updated"), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


@callback
def on_edit_price(update, context):
    new_price = update.message.text

    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    if not new_price.isdigit():
        msg = "\n".join(
            [
                _("That doesn't look like a valid price, please just give me a number"),
            ]
        )
        update.message.reply_text(msg, reply_markup=cancel_markup)
        return CONV_EDIT_PRICE

    with item:
        item.base_price = int(new_price)
    item.publish(context)
    update.message.reply_text(_("Price updated"))
    return ConversationHandler.END


@callback
def on_edit_min_price_inc(update, context):
    new_price = update.message.text

    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    if not new_price.isdigit():
        msg = "\n".join(
            [
                _("That doesn't look like a valid price, please just give me a number"),
            ]
        )
        update.message.reply_text(msg, reply_markup=cancel_markup)
        return CONV_EDIT_MIN_INC
    with item:
        item.min_price_inc = int(new_price)
    item.publish(context)
    update.message.reply_text(_("Minimum price increase updated"))
    return ConversationHandler.END


@callback
def on_edit_link(update, context):
    new_link = update.message.text

    item = Item.from_context(context)
    if item is None:
        update.message.reply_text(_("Something went wrong please try again"))
        return ConversationHandler.END

    with item:
        item.link = new_link
    item.publish(context)
    update.message.reply_text(_("Link updated"))
    return ConversationHandler.END


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

    edit_states = (
        (CONV_EDIT_TITLE, on_edit_title),
        (CONV_EDIT_DESCRIPTION, on_edit_description),
        (CONV_EDIT_CURRENCY, on_edit_currency),
        (CONV_EDIT_PRICE, on_edit_price),
        (CONV_EDIT_MIN_INC, on_edit_min_price_inc),
        (CONV_EDIT_LINK, on_edit_link),
    )
    yield from (
        InlineButtonCallback(item_delete_callback),
        InlineButtonCallback(item_publish_callback),
        InlineButtonCallback(item_close_callback),
        InlineButtonCallback(item_open_callback),
        ConversationHandler(
            entry_points=[InlineButtonCallback(item_edit_callback)],
            states={
                e[0]: [
                    canceler,
                    MessageHandler(Filters.text, e[1]),
                    InlineButtonCallback(item_edit_callback),
                ]
                for e in edit_states
            },
            fallbacks=[canceler, MessageHandler(Filters.command, abort)],
        ),
    )
