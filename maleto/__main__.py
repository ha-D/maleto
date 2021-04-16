
import logging

from telegram.ext import Updater
from telegram.ext import CommandHandler, Filters

from .item_start import item_start
from . import item_create, item_interact, item_bid, chat_member, admin

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def start(update, context):
    if len(context.args) == 0 or context.args[0] == '':
        update.message.reply_text('Hmm? Watchya wanna do?')
        return
    
    action, arg = context.args[0].split('-')
    if action == 'item':
        return item_start(update, context, arg)


def main():
    updater = Updater(token='1728955601:AAFvK3UD9nM2p0WTMOLUny9cIzPFDcqC2Hw', request_kwargs={'proxy_url': 'https://127.0.0.1:1087'}, use_context=True)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start, Filters.text), 0)

    modules = [item_create, item_interact, item_bid, chat_member, admin]
    for i, m in enumerate(modules):
        for handler in m.handlers():
            dispatcher.add_handler(handler, group=i+1)

    # 1772551576
    # updater.bot.send_message(chat_id=1772551576, text='Cool cool cool')
    updater.start_polling(allowed_updates=['message', 'callback_query', 'chat_member', 'my_chat_member'])
    # updater.start_polling()


if __name__ == '__main__':
    main()

