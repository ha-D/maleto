import logging

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .utils import Callback, bot_handler, split_keyboard, translator
from .utils.currency import get_currencies
from .item import Item

logger = logging.getLogger(__name__)

ITEM_TITLE, ITEM_PHOTO, ITEM_DESCRIPTION, ITEM_CURRENCY, ITEM_PRICE, ITEM_EMOJI = range(
    6
)
STORE_NAME = range(1)


cancel_markup = ReplyKeyboardMarkup([[KeyboardButton("Cancel")]])


@bot_handler
def item_new(update, context):
    item = Item.new(context.user.id)
    item.save()
    item.save_to_context(context)
    _ = translator(context.lang)
    msg = "\n".join(
        [
            _(
                "Ok lets add a new item. I'm going to ask you a few questions about the item you want to sell."
            ),
            _(
                "You can click on the `Cancel` button or enter `/cancel` at any time to abort"
            ),
            "",
            _("To start, enter the `title` of the item you want to sell"),
        ]
    )
    update.message.reply_text(
        msg, parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_markup
    )
    return ITEM_TITLE


@bot_handler
def item_title(update, context):
    _ = translator(context.lang)
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


def item_photo_ask(update, context, msg):
    _ = translator(context.lang)
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
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Done")], [KeyboardButton("Cancel")]]
        ),
    )
    return ITEM_PHOTO


@bot_handler
def item_photo(update, context):
    if len(update.message.photo) == 0:
        return ITEM_PHOTO

    photo = update.message.photo[0]
    # photo.get_file().download(f"media/{photo.file_id}")
    with Item.from_context(context) as item:
        item.photos.append(photo.file_id)

    return ITEM_PHOTO


@bot_handler
def item_photo_done(update, context):
    _ = translator(context.lang)
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
        return ITEM_PHOTO

    return item_description_ask(
        update,
        context,
        [
            _("Awesome! 🎉"),
        ],
    )


def item_description_ask(update, context, msg):
    _ = translator(context.lang)
    msg = "\n".join(
        [
            *msg,
            "",
            _("Now enter a `description` for your item"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_DESCRIPTION


@bot_handler
def item_description(update, context):
    with Item.from_context(context) as item:
        item.description = update.message.text
    return item_currency_ask(update, context, [])


def item_currency_ask(update, context, msg):
    _ = translator(context.lang)
    msg = "\n".join(
        [
            *msg,
            _("What `currency` would you like to use?"),
        ]
    )
    currencies = get_currencies(context)
    btns = split_keyboard([KeyboardButton(text=c) for c in currencies], 2)
    update.message.reply_text(msg, reply_markup=btns)
    return ITEM_CURRENCY


@bot_handler
def item_currency(update, context):
    _ = translator(context.lang)
    currency_key = get_currencies(context).get(update.message.text)
    if currency_key is None:
        update.message.reply_text(_("I'm not familiar with that currency, please try again"))
        return ITEM_CURRENCY

    with Item.from_context(context) as item:
        item.currency = currency_key

    return item_price_ask(update, context, [])


def item_price_ask(update, context, msg):
    _ = translator(context.lang)
    msg = "\n".join(
        [
            *msg,
            _("What `price` are you selling at?"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_PRICE


@bot_handler
def item_price(update, context):
    text = update.message.text
    _ = translator(context.lang)

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


def item_end(update, context, item):
    _ = translator(context.lang)
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
    item.active = (True,)
    item.new_settings_message(context, publish=True)


@bot_handler
def cancel(update, context):
    _ = translator(context.lang)
    item = Item.from_context(context)
    item.delete()
    Item.clear_context(context)
    update.message.reply_text(
        _("Ok, no worries, no item created."), reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


@bot_handler
def list_items(update, context):
    _ = translator(context.lang)
    items = Item.find(owner_id=context.user.id)
    if len(items) == 0:
        message = _(
            "You don't have any items. Use the `/newitem` command to create one."
        )
        update.message.reply_text(text=message, parse_mode=ParseMode.MARKDOWN)
    else:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        s.title,
                        callback_data=SelectItemCallback.data(s.id),
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
        update.message.reply_text(
            text=message, parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )


class SelectItemCallback(Callback):
    name = "select-item"

    def perform(self, context, query, item_id):
        _ = translator(context.lang)
        item = Item.find_by_id(item_id)
        # context.bot.edit_message_media(chat_id=context.user.id, message_id=query.message.message_id, media=InputMediaPhoto(media=item.photos[0]))
        query.edit_message_reply_markup(InlineKeyboardMarkup([]))
        with item:
            item.new_settings_message(context, publish=True)
        query.answer()


def handlers():
    canceler = MessageHandler(Filters.regex(r"/?[cC]ancel"), cancel)
    yield ConversationHandler(
        entry_points=[CommandHandler("newitem", item_new)],
        states={
            ITEM_TITLE: [canceler, MessageHandler(Filters.text, item_title)],
            ITEM_PHOTO: [
                canceler,
                MessageHandler(Filters.photo, item_photo),
                MessageHandler(Filters.regex(r"/?[dD]one"), item_photo_done),
            ],
            ITEM_DESCRIPTION: [
                canceler,
                MessageHandler(Filters.text, item_description),
            ],
            ITEM_CURRENCY: [canceler, MessageHandler(Filters.text, item_currency)],
            ITEM_PRICE: [canceler, MessageHandler(Filters.text, item_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        # run_async=True # Run sync break multiple images
    )

    yield from (CommandHandler("myitems", list_items), SelectItemCallback())
