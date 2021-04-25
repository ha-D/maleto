from babel import numbers

from .lang import _, convert_number


def get_currencies():
    return {
        _("US Dollars $"): "USD",
        _("Canadian Dollars $"): "CAD",
        _("Toman"): "TMN",
        _("Pound £"): "GBP",
        _("Euroes €"): "EUR",
        _("Turkish lira ₺"): "TRY",
    }


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
    num = numbers.format_number(num)
    return convert_number(num)