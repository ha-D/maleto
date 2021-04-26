import IPython

from dasdo.item import Item
from dasdo.user import User
from dasdo.chat import Chat


def start_shell(_bot):
    class context:
        bot = _bot
    bot = _bot

    IPython.embed(colors="neutral")
