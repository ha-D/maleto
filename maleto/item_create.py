import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import CommandHandler, ConversationHandler, Filters, MessageHandler

from maleto.core import metrics
from maleto.core.bot import (
    InlineButtonCallback,
    callback,
    inline_button_callback,
    trace,
)
from maleto.core.currency import get_currencies
from maleto.core.lang import _
from maleto.core.media import queue_file_download
from maleto.core.utils import split_keyboard
from maleto.item import Item

logger = logging.getLogger(__name__)

ITEM_TITLE, ITEM_PHOTO, ITEM_DESCRIPTION, ITEM_CURRENCY, ITEM_PRICE, ITEM_EMOJI = range(
    6
)
STORE_NAME = range(1)


cancel_markup = ReplyKeyboardMarkup([[KeyboardButton("Cancel")]])


@callback
def item_new(update, context):
    item = Item.new(context.user.id)
    item.save()
    item.save_to_context(context)
    msg = "\n".join(
        [
            _(
                "Ok lets add a new item. I'm going to ask you a few questions about the item you want to sell."
            ),
            _(
                "You can click on the `Cancel` button or enter `/cancel` at any time to abort"
            ),
            "",
            _("To start, enter the *title* of the item you want to sell"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    logger.info(
        f"Item creation started", extra=dict(item=item.id, user=context.user.id)
    )
    metrics.item_create_start.inc()
    return ITEM_TITLE


@callback
def item_title(update, context):
    title = update.message.text.strip()
    # TODO: title validations?
    with Item.from_context(context) as item:
        item.title = title

    return item_photo_ask(
        update,
        context,
        [
            _("Great thanks."),
        ],
    )


@trace
def item_photo_ask(update, context, msg):
    msg = "\n".join(
        [
            *msg,
            "",
            "📷 🖼",
            _("Now send me some `photos` of the item."),
            _(
                "Click on `Done` or enter `/done` when you've sent all the photos you want to add."
            ),
        ]
    )
    update.message.reply_text(
        msg,
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Done")], [KeyboardButton("Cancel")]]
        ),
    )
    return ITEM_PHOTO


@callback
def item_photo(update, context):
    if len(update.message.photo) == 0:
        return ITEM_PHOTO

    photo = update.message.photo[0]
    queue_file_download(photo.file_id)
    with Item.from_context(context) as item:
        item.photos.append(photo.file_id)

    return ITEM_PHOTO


@callback
def item_photo_done(update, context):
    item = Item.from_context(context)
    if len(item.photos) == 0:
        update.message.reply_text(
            "\n".join(
                [
                    _("Hmm, I haven't received any photos 🤔."),
                    "",
                    _(
                        "If you've sent photos please wait for the upload to finish and then notify me again."
                    ),
                ]
            )
        )
        metrics.item_create_no_photo.inc()
        return ITEM_PHOTO

    return item_description_ask(
        update,
        context,
        [
            _("Awesome! 🎉"),
        ],
    )


@trace
def item_description_ask(update, context, msg):
    msg = "\n".join(
        [
            *msg,
            "",
            _("Now enter a *description* for your item"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_DESCRIPTION


@callback
def item_description(update, context):
    with Item.from_context(context) as item:
        item.description = update.message.text
    return item_currency_ask(update, context, [])


@trace
def item_currency_ask(update, context, msg):
    msg = "\n".join(
        [
            *msg,
            _("What *currency* would you like to use?"),
        ]
    )
    currencies = get_currencies()
    btns = split_keyboard([KeyboardButton(text=c) for c in currencies], 2)
    update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(btns))
    return ITEM_CURRENCY


@callback
def item_currency(update, context):
    currency_key = get_currencies().get(update.message.text)
    if currency_key is None:
        update.message.reply_text(
            _("I'm not familiar with that currency, please try again")
        )
        return ITEM_CURRENCY

    with Item.from_context(context) as item:
        item.currency = currency_key

    return item_price_ask(update, context, [])


@trace
def item_price_ask(update, context, msg):
    msg = "\n".join(
        [
            *msg,
            _("What *price* are you selling at?"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_PRICE


@callback
def item_price(update, context):
    text = update.message.text

    if not text.isdigit():
        msg = "\n".join(
            [
                _("That doesn't look like a valid price, please just give me a number"),
            ]
        )
        update.message.reply_text(msg, reply_markup=cancel_markup)
        return ITEM_PRICE

    with Item.from_context(context) as item:
        item.base_price = int(text)
        item_end(update, context, item)

    return ConversationHandler.END


@trace
def item_end(update, context, item):
    msg = "\n".join(
        [
            _("Alright, thats all I need 🥳🥳"),
            "",
            _("There are more options you can edit later on."),
            "",
            _("You can view all your created items anytime by entering /myitems"),
        ]
    )
    update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
    item.active = True
    item.new_settings_message(context, publish=True)
    logger.info(
        f"Item creation successfully finished",
        extra=dict(item=item.id, user=context.user.id),
    )
    metrics.item_create_done.inc()


@callback
def cancel(update, context):
    item = Item.from_context(context)
    item.delete()
    Item.clear_context(context)
    update.message.reply_text(
        _("Ok, no worries, no item created."), reply_markup=ReplyKeyboardRemove()
    )
    logger.info(
        f"Item creation cancelled", extra=dict(item=item.id, user=context.user.id)
    )
    metrics.item_create_cancel.inc()
    return ConversationHandler.END


@callback
def list_items(update, context):
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
    canceler = MessageHandler(Filters.regex(r"/?[cC]ancel"), cancel)
    yield ConversationHandler(
        entry_points=[CommandHandler("newitem", item_new)],
        states={
            ITEM_TITLE: [canceler, MessageHandler(Filters.text, item_title)],
            ITEM_PHOTO: [
                canceler,
                # TODO: running async breaks uploading multiple images in a wierd way, check why
                MessageHandler(Filters.photo, item_photo, run_async=False),
                MessageHandler(Filters.regex(r"/?[dD]one"), item_photo_done),
            ],
            ITEM_DESCRIPTION: [
                canceler,
                MessageHandler(Filters.text, item_description),
            ],
            ITEM_CURRENCY: [canceler, MessageHandler(Filters.text, item_currency)],
            ITEM_PRICE: [canceler, MessageHandler(Filters.text, item_price)],
        },
        fallbacks=[canceler],
    )

    yield from (
        CommandHandler("myitems", list_items),
        InlineButtonCallback(select_item_callback),
    )
