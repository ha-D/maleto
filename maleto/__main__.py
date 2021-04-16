import logging
import argparse
from maleto.utils.config import EnvDefault

from telegram.ext import Updater
from telegram.ext import CommandHandler, Filters

from .item_start import item_start
from . import item_create, item_interact, item_bid, chat_member, admin

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def start(update, context):
    if len(context.args) == 0 or context.args[0] == "":
        update.message.reply_text("Hmm? Watchya wanna do?")
        return

    action, arg = context.args[0].split("-")
    if action == "item":
        return item_start(update, context, arg)


def main():
    parser = argparse.ArgumentParser(description="Sale Bot")
    parser.add_argument(
        "--token",
        "-t",
        type=str,
        help="Bot API token",
        action=EnvDefault,
        envvar="BOT_TOKEN",
        required=True,
    )
    parser.add_argument(
        "--proxy",
        type=str,
        help="Proxy used if polling",
        action=EnvDefault,
        envvar="BOT_PROXY",
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        help="Mode",
        choices=["poll", "webhook"],
        action=EnvDefault,
        envvar="BOT_MODE",
        default="poll",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="",
        action=EnvDefault,
        envar="BOT_HOST",
        default="0.0.0.0",
    )
    parser.add_argument(
        "--port", type=int, help="", action=EnvDefault, envvar="BOT_PORT", default=8443
    )
    parser.add_argument(
        "--url", "-u", type=str, help="", action=EnvDefault, envvar="BOT_URL"
    )

    args = parser.parse_args()
    if args.mode == "webhook" and not args.url:
        parser.error("--url option required in webhook mode")

    updater = Updater(
        token=args.token, request_kwargs={"proxy_url": args.proxy}, use_context=True
    )

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start, Filters.text), 0)

    modules = [item_create, item_interact, item_bid, chat_member, admin]
    for i, m in enumerate(modules):
        for handler in m.handlers():
            dispatcher.add_handler(handler, group=i + 1)

    if args.mode == "poll":
        updater.start_polling(
            allowed_updates=[
                "message",
                "callback_query",
                "chat_member",
                "my_chat_member",
            ]
        )
    elif args.mode == "webhook":
        updater.start_webhook(
            listen=args.host,
            port=args.port,
            url_path=args.token,
            webhook_url=f"{args.url}/{args.token}",
        )
    updater.idle()


if __name__ == "__main__":
    main()
