import IPython
from maleto.chat import Chat
from maleto.item import Item
from maleto.user import User


def start_shell(_bot):
    class context:
        bot = _bot

    bot = _bot

    IPython.embed(colors="neutral")
