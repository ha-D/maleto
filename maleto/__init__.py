import argparse
import logging
import os

from telegram.bot import Bot
from telegram.ext import Defaults, Updater
from telegram.parsemode import ParseMode
from telegram.utils.request import Request

from maleto import (
    chat_member,
    chat_settings,
    entry,
    item_bid,
    item_create,
    item_settings,
    user_settings,
)
from maleto.core import sentry
from maleto.core.config import EnvDefault
from maleto.core.logging import init_logging
from maleto.core.metrics import init_monitoring
from maleto.core.model import init_db
from maleto.core.shell import start_shell

__all__ = ("main",)


logger = logging.getLogger(__name__)
unhandled_error_logger = logging.getLogger(f"{__name__}.unhandled")


def get_version():
    import subprocess
    from importlib.metadata import version

    try:
        return (
            subprocess.check_output(["git", "describe", "--tags"])
            .strip()
            .decode("utf-8")
        )
    except:
        return version(__name__)


__version__ = get_version()


def cmd_start(args):
    logger.info(f"Starting bot in {args.mode} mode")

    sentry.init_sentry(
        args.sentry_dsn,
        version=__version__,
        ignore_loggers=[unhandled_error_logger.name, "httplib"],
    )
    init_db(args.db_uri)
    init_monitoring(args.metrics_port)

    defaults = Defaults(parse_mode=ParseMode.MARKDOWN, run_async=True)
    updater = Updater(
        token=args.token,
        request_kwargs={"proxy_url": args.proxy},
        use_context=True,
        defaults=defaults,
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
    init_db(args.db_uri)
    bot = Bot(args.token, request=Request(proxy_url=args.proxy))

    start_shell(bot)


def on_error(update, context):
    unhandled_error_logger.error("Unhandled exception", exc_info=context.error)


def read_config_envs():
    try:
        with open("config.env") as f:
            for num, line in enumerate(f.readlines()):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                eqpos = line.index("=")
                if eqpos == -1:
                    raise ValueError(f"Invalid config.env file at line {num + 1}")
                key, val = line[:eqpos], line[eqpos + 1 :]
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
        help="Telegram Bot API token",
        action=EnvDefault,
        envvar="BOT_TOKEN",
        required=True,
    )
    parser.add_argument(
        "--proxy",
        type=str,
        help="Proxy to use for connecting to Telegram API server. Only used in 'poll' mode.",
        action=EnvDefault,
        envvar="BOT_PROXY",
        required=False,
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        help="Specifies the method to use for receiving updates from Telegram.",
        choices=["poll", "webhook"],
        action=EnvDefault,
        envvar="BOT_MODE",
        default="poll",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="The host address to listen to for incoming webhook requests. Only used in 'webhook' mode.",
        action=EnvDefault,
        envvar="BOT_HOST",
        default="0.0.0.0",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="The port to listen on for incoming webhook requests. Only used in 'webhook' mode.",
        action=EnvDefault,
        envvar="BOT_PORT",
        default=8443,
    )
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        help="The URL which Telegram should send updates to if using 'webhook' mode",
        action=EnvDefault,
        envvar="BOT_URL",
        required=False,
    )
    parser.add_argument(
        "--db-uri",
        "-d",
        type=str,
        help="MongoDB URI to connect to. Use 'mem' to use an in-memory database.",
        action=EnvDefault,
        envvar="BOT_MONGO_URI",
        default="mongodb://127.0.0.1:27017",
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
        type=int,
        help="",
        action=EnvDefault,
        envvar="BOT_METRICS_PORT",
        required=False,
    )
    parser.add_argument(
        "--log-file",
        "-o",
        type=str,
        help="The file to write log messages to. Will log to stdout/stderr if not specified.",
        action=EnvDefault,
        envvar="BOT_LOG_FILE",
        required=False,
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        help="The minimum level at which messages are logged",
        action=EnvDefault,
        envvar="BOT_LOG_LEVEL",
        default="INFO",
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
    if args.log_level.lower() not in ["debug", "info", "warning", "error", "critical"]:
        parser.error(f"Invalid log level: {args.log_level}")

    init_logging(args.log_file, args.log_level)
    logger.info(f"Running version {__version__}")

    {"start": cmd_start, "setcommands": cmd_commands, "shell": cmd_shell,}[
        args.command
    ](args)
