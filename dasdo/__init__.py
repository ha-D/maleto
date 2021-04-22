from importlib.metadata import version
import logging
import argparse

from telegram.bot import Bot
from telegram.ext import Updater
from telegram.utils.request import Request
import sentry_sdk

from .utils.model import init_db
from .utils.config import EnvDefault
from . import (
    entry,
    item_bid,
    item_create,
    item_settings,
    chat_member,
    chat_settings,
    user_settings,
)

__version__ = version(__name__)
__all__ = ("main",)


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def cmd_start(args):
    logger.info(f"Starting bot in {args.mode} mode")

    if args.sentry_dsn:
        sentry_sdk.init(args.sentry_dsn, traces_sample_rate=1.0)

    init_db(args.db_uri, args.db_name)

    updater = Updater(
        token=args.token, request_kwargs={"proxy_url": args.proxy}, use_context=True
    )

    dispatcher = updater.dispatcher
    if args.sentry_dsn:
        dispatcher.add_error_handler(on_error_sentry)
    dispatcher.add_error_handler(on_error)

    modules = [
        entry,
        item_bid,
        item_create,
        item_settings,
        chat_member,
        chat_settings,
        user_settings,
    ]
    for i, m in enumerate(modules):
        for handler in m.handlers():
            dispatcher.add_handler(handler, group=i)

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


def cmd_commands(args):
    bot = Bot(args.token, request=Request(proxy_url=args.proxy))

    bot.set_my_commands(
        [
            ("newitem", "Create new item"),
            ("myitems", "List created items"),
            ("changelang", "Change your preferred language"),
        ]
    )


def on_error_sentry(update, context):
    sentry_sdk.capture_exception(context.error)


def on_error(update, context):
    logger.exception(context.error)


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
        required=False,
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
        envvar="BOT_HOST",
        default="0.0.0.0",
    )
    parser.add_argument(
        "--port", type=int, help="", action=EnvDefault, envvar="BOT_PORT", default=8443
    )
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_URL",
        required=False,
    )
    parser.add_argument(
        "--db-uri",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_DB_URI",
        default="mongodb://127.0.0.1:27017",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_DB_NAME",
        default="maleto",
    )
    parser.add_argument(
        "--sentry-dsn",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_SENTRY_DSN",
        required=False,
    )
    parser.add_argument(
        "--metrics-port",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_METRICS_PORT",
        required=False,
    )

    parser.add_argument(
        "command",
        metavar="command",
        type=str,
        choices=["start", "setcommands"],
        nargs="?",
        default="start",
    )

    args = parser.parse_args()
    if args.mode == "webhook" and not args.url:
        parser.error("--url option required in webhook mode")

    {"start": cmd_start, "setcommands": cmd_commands}[args.command](args)
