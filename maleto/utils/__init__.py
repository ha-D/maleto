from functools import wraps
import logging
import time

from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers
from bson.objectid import ObjectId
from bson.int64 import Int64
from threading import Lock
from collections import defaultdict

from maleto.utils.lang import uselang

logger = logging.getLogger(__name__)


class Callback(CallbackQueryHandler):
    name = None

    def __init__(self, item=None):
        super().__init__(self._perform, pattern=f"^{self.name}(#.+)*$")

    @classmethod
    def data(cls, *args):
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

        return "#".join([cls.name, *pargs])

    def _perform(self, update, context):
        from maleto.user import User
        from maleto.chat import Chat

        user = User.create_or_update_from_api(update.effective_user)
        context.user = user

        context.chat = Chat.find_by_id(update.effective_chat.id)

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

        with uselang(user.lang):
            return self.perform(context, update.callback_query, *args)


def find_by(lst, field, val):
    for i in range(len(lst)):
        if lst[i][field] == val:
            return lst[i], i
    return None, -1


def omit(d, x):
    return {k: d[k] for k in d if k not in x}


context_locks = defaultdict(Lock)
context_main_lock = Lock()


def lock_context_for_user(context, user):
    with context_main_lock:
        return context_locks[user.id]


def find_best_inc(price):
    from math import floor, log

    if price < 10:
        return 1
    if price < 100:
        return 5
    if price < 200:
        return 20
    if price < 1000:
        return 50
    if price < 10000:
        return 200
    return find_best_inc(price // 1000) * 1000


def split_keyboard(btns, cols=2):
    from itertools import zip_longest as zl

    rows = zl(*[btns[i::cols] for i in range(cols)])
    return [[x for x in row if x is not None] for row in rows]


def bot_handler(f):
    @wraps(f)
    def inner(update, context):
        from maleto.user import User
        from maleto.chat import Chat

        api_user = update.effective_user
        user = User.create_or_update_from_api(api_user)
        context.user = user
        context.chat = Chat.find_by_id(update.effective_chat.id)
        with uselang(user.lang):
            return f(update, context)

    return inner


def trace(f):
    @wraps(f)
    def inner(*args, **kwargs):
        before = time.perf_counter()
        result = f(*args, **kwargs)
        extra = None
        for arg in args:
            if type(arg) == CallbackContext:
                extra = {"user": arg.user.id, "username": arg.user.username}
                break
        tm = time.perf_counter() - before
        logger.debug(
            f"trace call [{f.__module__}.{f.__name__}] time:{tm:.2f}s", extra=extra
        )
        return result

    return inner


bot = None


def get_bot(context):
    global bot
    if bot is None:
        bot = context.bot.get_me()
    return bot


def parse_start_params(params_str):
    kwargs = {}
    for arg in params_str.split('-'):
        if not arg:
            continue
        key, val = arg.split('_')
        kwargs[key] = val
    return kwargs
        

def create_start_params(**params):
    return '-'.join([f"{k}_{params[k]}" for k in params])