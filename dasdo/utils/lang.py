import gettext
import threading
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

__all__ = ("_", "uselang", "LANGUAGES", "current_lang")

LANGUAGES = {"English": "en", "فارسی": "fa"}

translator_cache = {}
thread_langs = {}


def get_translator(lang):
    if lang is None:
        lang = "en"
    if lang not in translator_cache:
        gt = gettext.translation(
            "messages", "translations", fallback=True, languages=[lang]
        )
        translator_cache[lang] = gt.gettext
    return translator_cache[lang]


def current_lang():
    tid = threading.current_thread().ident
    return thread_langs.get(tid)


def _(msg, lang=None):
    if lang is None:
        lang = current_lang()
    return get_translator(lang)(msg)


class LangContext:
    def __init__(self, lang):
        self.lang = lang

    def __enter__(self):
        tid = threading.current_thread().ident
        thread_langs[tid] = self.lang
        return self

    def __exit__(self, type, value, traceback):
        tid = threading.current_thread().ident
        if tid in thread_langs:
            del thread_langs[tid]


def uselang(lang):
    return LangContext(lang)


def convert_number(num, lang=None):
    if lang is None:
        lang = current_lang()
    if lang == "fa":
        diff = ord("۱") - ord("1")
        return "".join([chr(ord(s) + diff) if s.isdigit() else s for s in str(num)])
    return str(num)