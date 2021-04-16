import logging

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .utils import bot_handler, translator
from .item import Item
from .user import User

logger = logging.getLogger(__name__)

ITEM_TITLE, ITEM_PHOTO, ITEM_DESCRIPTION, ITEM_PRICE, ITEM_EMOJI = range(5)
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
                "Ok lets add a new item. I'm going to ask you some questions about the item you want to sell."
            ),
            _(
                "You can click on the 'Cancel' button or enter /cancel at any time to abort"
            ),
            "",
            _("To start, enter the *title* of the item you want to sell"),
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
        msg = "\n".join(
            [
                _("Great thanks."),
                "",
                "📷 🖼",
                _("Now send me some *photos* of the item."),
                _(
                    "Click on Done or enter /done when you've sent all the photos you want to add."
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
    with Item.from_context(context) as item:
        if len(item.photos) == 0:
            update.message.reply_text(
                "\n".join(
                    [
                        _("Hmm, I haven't received any photos 🤔."),
                        "",
                        _(
                            "If you've sent any photos please wait for the upload to finish and then notify me again."
                        ),
                    ]
                )
            )
            return ITEM_PHOTO

    msg = "\n".join(
        [
            _("Awesome! 🎉"),
            "",
            _("Now enter a description about your item"),
        ]
    )
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_DESCRIPTION


@bot_handler
def item_description(update, context):
    with Item.from_context(context) as item:
        item.description = update.message.text

    _ = translator(context.lang)
    msg = "\n".join(
        [
            _("What price are you selling at?"),
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
            _("You can view all your created items anytime by entering /listitems"),
        ]
    )
    update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())

    user = update.effective_user
    msg = update.message.reply_photo(item.photos[0], caption=_("Please wait..."))
    item.active = (True,)
    item.change_user_interaction_message(context, user.id, msg.message_id)
    item.publish_to_interaction_message_for_user(context, user.id)


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
    _ = translator(context.user)
    items = Item.find(owner=context.user.id)
    if len(items) == 0:
        message = _(
            "You don't have any items. Use the _/newitem_ command to create one."
        )
    else:
        message = "\n".join(
            [
                _("Click on one any item to view more options"),
                "\n",
                *[s.link() for s in items],
            ]
        )
    update.message.reply_text(text=message, parse_mode=ParseMode.MARKDOWN)


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
            ITEM_PRICE: [canceler, MessageHandler(Filters.text, item_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        # run_async=True # Run sync break multiple images
    )

    yield CommandHandler("listitems", list_items)
