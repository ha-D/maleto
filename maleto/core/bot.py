import logging
import time
from functools import wraps

from bson.int64 import Int64
from bson.objectid import ObjectId
from maleto.core import metrics, sentry
from maleto.core.lang import uselang
from telegram.ext import CallbackContext, CallbackQueryHandler

logger = logging.getLogger(__name__)


def inline_button_callback(name):
    def get_data(*args):
        pargs = []
        for a in args:
            if type(a) is str:
                pargs.append(f"str!{str(a)}")
            elif type(a) is int:
                pargs.append(f"int!{str(a)}")
            elif type(a) is Int64:
                pargs.append(f"int64!{str(a)}")
            elif type(a) is ObjectId:
                pargs.append(f"id!{str(a)}")

        return "#".join([name, *pargs])

    def outer(f):
        @wraps(f)
        def inner(update, context):
            query = update.callback_query
            parts = query.data.split("#")
            args = []
            for a in parts[1:]:
                xp = a.split("!")
                if xp[0] == "str":
                    args.append(xp[1])
                elif xp[0] == "int":
                    args.append(int(xp[1]))
                elif xp[0] == "int64":
                    args.append(Int64(xp[1]))
                elif xp[0] == "id":
                    args.append(ObjectId(xp[1]))
            return callback(f)(update, context, *args)

        inner.data = get_data
        inner.name = name
        return inner

    return outer


def InlineButtonCallback(callback):
    return CallbackQueryHandler(callback, pattern=f"^{callback.name}(#.+)*$")


def callback(f):
    @sentry.transaction
    @wraps(f)
    def inner(update, context, *args, **kwargs):
        from maleto.chat import Chat
        from maleto.user import User

        before = time.perf_counter()

        try:
            api_user = update.effective_user
            user = User.create_or_update_from_api(api_user)
            chat = Chat.create_or_update_from_api(context, update.effective_chat)
            context.user = user
            context.chat = chat
            sentry.set_user(user)
            with uselang(user.lang):
                result = f(update, context, *args, **kwargs)
            metrics.request_success.labels(f.__name__).inc()
        except:
            metrics.request_error.labels(f.__name__).inc()
            raise

        tm = time.perf_counter() - before
        metrics.request_time.labels(f.__name__).observe(tm)
        logger.debug(
            f"trace call [{f.__module__}.{f.__name__}] time:{tm:.2f}s",
            extra=dict(user=user.id, username=user.username),
        )
        return result

    return inner


def trace(f):
    @sentry.span
    @wraps(f)
    def inner(*args, **kwargs):
        before = time.perf_counter()
        result = f(*args, **kwargs)
        extra = None
        for arg in args:
            # Need the none check since @trace is sometimes used without @callback being present
            if type(arg) == CallbackContext and getattr(arg, "user", None) is not None:
                extra = {"user": arg.user.id, "username": arg.user.username}
                break
        tm = time.perf_counter() - before
        logger.debug(
            f"trace call [{f.__module__}.{f.__name__}] time:{tm:.2f}s", extra=extra
        )
        return result

    return inner


_bot = None


def get_bot(context):
    global _bot
    if _bot is None:
        _bot = context.bot.get_me()
    return _bot


def parse_start_params(params_str):
    kwargs = {}
    for arg in params_str.split("-"):
        if not arg:
            continue
        key, val = arg.split("_")
        kwargs[key] = val
    return kwargs


def create_start_params(**params):
    return "-".join([f"{k}_{params[k]}" for k in params])
