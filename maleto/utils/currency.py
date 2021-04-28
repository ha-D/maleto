from babel import Locale, numbers

from .lang import _, convert_number, current_lang, deconvert_number


def get_currencies():
    return {
        _("US Dollars $"): "USD",
        _("Canadian Dollars $"): "CAD",
        _("Toman"): "TMN",
        _("Pound £"): "GBP",
        _("Euroes €"): "EUR",
        _("Turkish lira ₺"): "TRY",
    }


def currency_name(currency_code):
    currencies = get_currencies()
    for name, code in currencies.items():
        if code == currency_code:
            return name
    return ""


def format_currency(currency, price):
    price = format_number(price)
    m = {
        "USD": _("${}").format(price),
        "CAD": _("${}").format(price),
        "GBP": _("£{}").format(price),
        "EUR": _("€{}").format(price),
        "TMN": _("{} Toman").format(price),
    }
    if currency not in m:
        currency = "USD"
    return m[currency]


def format_number(num):
    lang = current_lang()
    if lang is None or lang == '':
        lang = 'en'
    locale = Locale(lang)
    num = numbers.format_number(num, locale)
    return convert_number(num)


def deformat_number(num):
    num = str(num).replace(",", "")
    return deconvert_number(num)
