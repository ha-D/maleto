import logging

from telegram import *
from telegram.ext import *
from telegram.utils.helpers import *

logger = logging.getLogger(__name__)


def find_by(lst, field, val):
    for i in range(len(lst)):
        if lst[i][field] == val:
            return lst[i], i
    return None, -1


def omit(d, x):
    return {k: d[k] for k in d if k not in x}


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
