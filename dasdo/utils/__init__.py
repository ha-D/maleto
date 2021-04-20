
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *
from telegram.utils import helpers
from bson.objectid import ObjectId
from bson.int64 import Int64
from threading import Lock
from collections import defaultdict


class Callback(CallbackQueryHandler):
    name = None

    def __init__(self, item=None):
        super().__init__(self._perform, pattern=f'^{self.name}(#.+)*$')

    @classmethod
    def data(cls, *args):
        pargs = []
        for a in args:
            if type(a) is str:
                pargs.append(f'str!{str(a)}')
            elif type(a) is int:
                pargs.append(f'int!{str(a)}')
            elif type(a) is Int64:
                pargs.append(f'int64!{str(a)}')
            elif type(a) is ObjectId:
                pargs.append(f'id!{str(a)}')

        return '#'.join([cls.name, *pargs])

    def _perform(self, update, context):
        from ..user import User

        user = User.create_or_update_from_api(update.effective_user)
        context.user = user
        context.lang = user.lang

        query = update.callback_query
        parts = query.data.split('#')
        args = []
        for a in parts[1:]:
            xp = a.split('!')
            if xp[0] == 'str':
                args.append(xp[1])
            elif xp[0] == 'int':
                args.append(int(xp[1]))
            elif xp[0] == 'int64':
                args.append(Int64(xp[1]))
            elif xp[0] == 'id':
                args.append(ObjectId(xp[1]))
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
    def inner(update, context):
        from ..user import User
        api_user = update.effective_user
        user = User.create_or_update_from_api(api_user)
        context.user = user
        context.lang = user.lang
        return f(update, context)
    return inner


bot = None
def get_bot(context):
    global bot
    if bot is None:
        bot = context.bot.get_me()
    return bot



import gettext

lang_cache = {}
def translator(lang):
    if lang is None:
        lang = 'en'
    if lang not in lang_cache:
        gt = gettext.translation('messages', 'translations', fallback=True, languages=[lang])
        lang_cache[lang] = gt.gettext
    return lang_cache[lang]
    
LANGUAGES = {"English": "en", "فارسی": "fa"}