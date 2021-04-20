from . import translator


def get_currencies(context):
    _ = translator(context.lang)
    return {
        _("US Dollars $"): "USD",
        _("Canadian Dollars $"): "CAD",
        _("Toman"): "TMN",
        _("Pound £"): "GBP",
        _("Euroes €"): "EUR",
        _("Turkish lira ₺"): "TRY",
    }
    

def format_currency(context, currency, price):
    _ = translator(context.lang)
    m = {
        "USD": _("${}").format(price),
        "CAD": _("${}").format(price),
        "GBP": _("£{}").format(price),
        "EUR": _("€{}").format(price),
        "TMN": _("{} Toman").format(price),
    }
    if currency not in m:
        currency = 'USD'
    return m[currency]