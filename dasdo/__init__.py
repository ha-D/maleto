import argparse
import logging
import os
from importlib.metadata import version

from telegram.bot import Bot
from telegram.ext import Updater
from telegram.utils.request import Request

from dasdo import (
    chat_member,
    chat_settings,
    entry,
    item_bid,
    item_create,
    item_settings,
    user_settings,
)
from dasdo.utils import sentry
from dasdo.utils.config import EnvDefault
from dasdo.utils.model import init_db
from dasdo.utils.shell import start_shell

__version__ = version(__name__)
__all__ = ("main",)


logging.getLogger("telegram.ext.updater").setLevel(logging.INFO)
logging.getLogger("telegram.bot").setLevel(logging.INFO)
logging.getLogger("telegram.ext.dispatcher").setLevel(logging.INFO)
logging.getLogger("telegram.ext.conversationhandler").setLevel(logging.INFO)
logging.getLogger("telegram.ext.utils.webhookhandler").setLevel(logging.INFO)
logging.getLogger("apscheduler.scheduler").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


def cmd_start(args):
    logger.info(f"Starting bot in {args.mode} mode")

    sentry.init_sentry(args.sentry_dsn)
    init_db(args.db_uri, args.db_name)

    updater = Updater(
        token=args.token, request_kwargs={"proxy_url": args.proxy}, use_context=True
    )

    dispatcher = updater.dispatcher
    dispatcher.add_error_handler(sentry.on_error)
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


def cmd_shell(args):
    init_db(args.db_uri, args.db_name)
    bot = Bot(args.token, request=Request(proxy_url=args.proxy))

    start_shell(bot)


def on_error(update, context):
    logger.exception(context.error)


def read_config_envs():
    try:
        with open("config.env") as f:
            for num, line in enumerate(f.readlines()):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.count("=") != 1:
                    raise ValueError(f"Invalid config.env file at line {num + 1}")
                key, val = line.split("=")
                if val[0] in ['"', "'"] and val[-1] == val[0]:
                    val = val[1:-1]
                os.environ[key.strip()] = val.strip()
    except FileNotFoundError:
        raise


def main():
    read_config_envs()

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
        "--log",
        type=str,
        help="",
        action=EnvDefault,
        envvar="BOT_LOG_FILE",
        required=False,
    )

    parser.add_argument(
        "command",
        metavar="command",
        type=str,
        choices=["start", "setcommands", "shell"],
        nargs="?",
        default="start",
    )

    args = parser.parse_args()
    if args.mode == "webhook" and not args.url:
        parser.error("--url option required in webhook mode")

    log_args = {"filename": args.log, "filemode": "a"} if args.log else {}
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
        **log_args,
    )

    {"start": cmd_start, "setcommands": cmd_commands, "shell": cmd_shell,}[
        args.command
    ](args)