import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from utils import handler
from item import Item

logger = logging.getLogger(__name__)

ITEM_TITLE, ITEM_PHOTO, ITEM_DESCRIPTION, ITEM_PRICE, ITEM_EMOJI = range(5)
STORE_NAME = range(1)


cancel_markup = ReplyKeyboardMarkup([[KeyboardButton('Cancel')]])

@handler
def item_new(update, context):
    item = Item()
    item.owner_id = update.effective_user.id
    item.save()
    item.save_to_context(context)
    msg = '\n'.join([
        "Ok lets add a new item. I'm going to ask you some questions about the item you want to sell.",
        "You may click on the 'Cancel' button or enter /cancel at any time to abort",
        '',
        'Please enter the *title* of the item you want to sell',
    ])
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_markup)
    return ITEM_TITLE 


@handler
def item_title(update, context):
    title = update.message.text.strip()
    # TODO: title validations?
    with Item.from_context(context) as item:
        item.title = title
        msg = '\n'.join([
            'Great thanks.',
            '',
            '📷 🖼',
            'Now send me some *photos* of the item.',
            "Click on Done or enter /done when you've sent all the photos you want to add."
        ])
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardMarkup([[KeyboardButton('Done')], [KeyboardButton('Cancel')]]))
        return ITEM_PHOTO


@handler
def item_photo(update, context):
    if len(update.message.photo) == 0:
        return ITEM_PHOTO

    photo = update.message.photo[0] 
    photo.get_file().download(f'media/{photo.file_id}')
    with Item.from_context(context) as item:
        item.photos.append(photo.file_id)

    return ITEM_PHOTO


@handler
def item_photo_done(update, context):
    with Item.from_context(context) as item:
        if len(item.photos) == 0:
            update.message.reply_text('\n'.join([
                "Hmm, I haven't received any photos 🤔.",
                "",
                "If you've sent any photos please wait for the upload to finish and then notify me again."
            ]))
            return ITEM_PHOTO
   
    msg = '\n'.join([
        'Awesome! 🎉',
        '',
        'Now enter a description about your item',
    ])
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_DESCRIPTION


@handler
def item_description(update, context):
    with Item.from_context(context) as item:
        item.description = update.message.text

    msg = '\n'.join([
        "What price are you selling at?",
    ])
    update.message.reply_text(msg, reply_markup=cancel_markup)
    return ITEM_PRICE


@handler
def item_price(update, context):
    user = update.effective_user
    text = update.message.text

    if not text.isdigit():
        msg = '\n'.join([
          "That doesn't look like a valid price, please just give me a number",
        ])
        update.message.reply_text(msg, reply_markup=cancel_markup)
        return ITEM_PRICE
    
    with Item.from_context(context) as item:
        item.base_price = int(text)
        item_end(update, context, item)
    return ConversationHandler.END


def item_end(update, context, item):
    msg = '\n'.join([
        "Alright, thats all I need 🥳🥳",
        '',
        'There are more options you can edit later on.',
        '',
        'You can view all your created items anytime by entering /listitems'
    ])
    update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())

    user = update.effective_user
    msg = update.message.reply_photo(item.photos[0], caption='Please wait...')
    item.active = True,
    item.change_user_interaction_message(context, user.id, msg.message_id)
    item.publish_to_interaction_message_for_user(context, user.id)


@handler
def cancel(update, context):
    item = Item.from_context(context)
    item.delete()
    Item.clear_context(context)
    update.message.reply_text('Ok, no worries, no item created.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


@handler
def list_items(update, context):
    user = update.effective_user
    items = Item.find(owner=user.id)
    if len(items) == 0:
        message = "You don't have any items. Use the _/newitem_ command to create one."
    else:
        message = '\n'.join([
            'Click on one any item to view more options',
            '\n',
            *[s.link() for s in items],
        ])
    update.message.reply_text(text=message, parse_mode=ParseMode.MARKDOWN)


def handlers():
    canceler = MessageHandler(Filters.regex(r'/?[cC]ancel'), cancel)
    yield ConversationHandler(
        entry_points=[CommandHandler('newitem', item_new)],
        states={
            ITEM_TITLE: [canceler, MessageHandler(Filters.text, item_title)],
            ITEM_PHOTO: [canceler, MessageHandler(Filters.photo, item_photo), MessageHandler(Filters.regex(r'/?[dD]one'), item_photo_done)],
            ITEM_DESCRIPTION: [canceler, MessageHandler(Filters.text, item_description)],
            ITEM_PRICE: [canceler, MessageHandler(Filters.text, item_price)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        # run_async=True # Run sync break multiple images
    )

    yield CommandHandler('listitems', list_items)

