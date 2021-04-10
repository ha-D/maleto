import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers
import IPython
import callbacks as cb

from models import Item
from utils import Callback, find_best_inc, handler

logger = logging.getLogger(__name__)

OPTIONS, OFFER = range(2)


# @handler
def start(update, context):
    if len(context.args) == 0:
        update.message.reply_text('Hmm? Watchya wanna do?')
        return
    
    action, arg = context.args[0].split('-')
    if action == 'item':
        return start_item(update, context, arg)
    # elif action == 'chat':
    #     return start_chat(update, context, arg)


def start_item(update, context, item_id):
    user = update.message.from_user
    with Item.find_by_id(item_id) as item:
        item.save_to_context(context)
        msg = update.message.reply_photo(item.photos[0], caption='Please wait...')
        item.change_user_interaction_message(context, user.id, msg.message_id)
        item.publish_to_interaction_message_for_user(context, user.id)


# def start_chat(update, context, chat_id):
#     user = update.message.from_user
#     with Chat.find_by_id(chat_id) as chat:
#         item.save_to_context(context)
#         msg = update.message.reply_photo(item.photos[0], caption='Please wait...')
#         item.change_user_interaction_message(context, user.id, msg.message_id)
#         item.publish_to_interaction_message_for_user(context, user.id)
     
     
class RevokeCallback(Callback):
    name = cb.REVOKE

    def perform(self, context, query, item_id):
        user = query.from_user
        with Item.find_by_id(item_id) as item:
            item.publish_to_interaction_message_for_user(context, user.id)
            _, pos_in_queue, _ = item.get_latest_bids(user.id)
            if pos_in_queue < 0:
                query.answer('Not in queue')
            else:
                item.remove_user_from_bids(user.id)
                item.publish_to_messages(context)
                query.answer('Offer removed')

class DeleteCallback(Callback):
    name = cb.DELETE_ITEM

    def perform(self, context, query, item_id, action=''):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            if action == '':
                item.change_interaction_message_state(user.id, 'deleting')
                item.publish_to_interaction_message_for_user(context, user.id)
                query.answer()
            elif action == 'yes':
                item.delete_all_messages(context, user.id)
                item.delete()
                query.answer('Item deleted')
            elif action == 'no':
                item.change_interaction_message_state(user.id, 'default')
                item.publish_to_interaction_message_for_user(context, user.id)
                query.answer()


class EditCallback(Callback):
    name = cb.EDIT_ITEM

    def perform(self, context, query, item_id, action=''):
        context.bot.send_message(chat_id=query.message.chat.id, text='Editing is not available yet, sorry')
        query.answer()


class BidCallback(Callback):
    name = cb.BID

    def perform(self, context, query, item_id):
        with Item.find_by_id(item_id) as item:
            ask_for_bid(context, query.message, item)
            return OFFER


class SameBidCallback(Callback):
    name = cb.BID_SAME

    def perform(self, context, query, item_id, price):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            try:
                item.add_user_bid(user.id, price)
                item.publish_to_messages(context)
                query.answer('Done')
            except ValueError as e:
                item.publish_to_interaction_message_for_user(context, user.id)
                query.answer(e.message)


def ask_for_bid(context, message, item, error=None):
    item.save_to_context(context)
    price, _, _ = item.get_latest_bids()

    min_price_inc = item.min_price_inc or find_best_inc(item.base_price)
    prices = [price + min_price_inc * i for i in range(3)]
    msg = 'Enter your offer'
    if error is not None:
        msg = f'{error}\n{msg}'
    message.reply_markdown(
        text=msg,
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(str(p)) for p in prices]])
    )
            

@handler
def on_bid(update, context):
    with Item.from_context(context) as item:
        price = int(update.message.text)
        user = update.message.from_user
        try:
            item.add_user_bid(user.id, price)
            update.message.reply_text('Thanks you have it', reply_markup=ReplyKeyboardRemove())
            item.clear_context(context)
            item.publish_to_messages(context)
            return ConversationHandler.END
        except ValueError as e:
            update.message.reply_text('Could not do it:', reply_markup=ReplyKeyboardRemove())
            ask_for_bid(context, update.message, item, 'Could not do it sorry')
            return OFFER



class PublishToStoreCallback(Callback):
    name = cb.PUBLISH_TO_STORE

    def perform(self, context, query, item_id, action='', chat_id=None):
        with Item.find_by_id(item_id) as item:
            user = query.from_user
            if action == '':
                item.change_interaction_message_state(user.id, 'publishing')
            elif action == 'cancel':
                item.change_interaction_message_state(user.id, 'default')
            elif action == 'add':
                item.add_sale_message(context, chat_id)
            elif action == 'rem':
                item.remove_sale_message(context, chat_id)
            item.publish_to_interaction_message_for_user(context, user.id)
            query.answer()


@handler
def cancel(update, context):
    Item.C(context, remove=True)
    update.message.reply_text(
        'Ok cool, nothing happened', reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def setup(dispatcher):
    dispatcher.add_handler(CommandHandler('start', start, Filters.text))
    dispatcher.add_handler(ConversationHandler(
        entry_points=[RevokeCallback(), BidCallback(), SameBidCallback(), DeleteCallback(), EditCallback() ],
        states={
            OFFER: [
                MessageHandler(Filters.text, on_bid)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    ))

    dispatcher.add_handler(PublishToStoreCallback())





