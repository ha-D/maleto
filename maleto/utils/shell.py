import IPython

from maleto.item import Item
from maleto.user import User
from maleto.chat import Chat


def start_shell(_bot):
    class context:
        bot = _bot
    bot = _bot

    IPython.embed(colors="neutral")
