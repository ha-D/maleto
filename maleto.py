
import logging
import admin
import bid
import inline
from telegram.ext import Updater


logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    updater = Updater(token='1728955601:AAFvK3UD9nM2p0WTMOLUny9cIzPFDcqC2Hw', request_kwargs={'proxy_url': 'https://127.0.0.1:8080'}, use_context=True)

    dispatcher = updater.dispatcher
    admin.setup(dispatcher)
    inline.setup(dispatcher)
    bid.setup(dispatcher)

    # 1772551576
    # updater.bot.send_message(chat_id=1772551576, text='Cool cool cool')
    updater.start_polling(allowed_updates=['message', 'callback_query', 'chat_member', 'my_chat_member'])
    # updater.start_polling()


if __name__ == '__main__':
    main()

