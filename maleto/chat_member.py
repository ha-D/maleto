import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .utils import get_bot
from .chat import Chat
from .user import User

logger = logging.getLogger(__name__)


def on_member(update, context):
    cm = update.chat_member
    handle_chat_member(cm.new_chat_member, cm.chat)


def on_bot_member(update, context):
    if update.my_chat_member.new_chat_member.status != 'administrator':
        return
    create_chat(update, context)
    members = context.bot.get_chat_administrators(update.effective_chat.id)
    for member in members:
        if not member.user.is_bot:
            handle_chat_member(member, update.effective_chat)


def handle_chat_member(chat_member, chat):
    user, status = chat_member.user, chat_member.status
    try:
        seller = User.find_one(id=user.id)
    except ValueError:
        seller = User(id=user.id, username=user.username, first_name=user.first_name, last_name=user.last_name)
    exists = any(c['chat_id'] == chat.id for c in seller.chats)
    if status in ['member', 'creator'] and not exists:
        seller.chats.append({'chat_id': chat.id, 'name': chat.title})
    elif status == 'left' and exists:
        seller.chats = [c for c in seller.chats if c['chat_id'] != chat.id]
    seller.save()


def create_chat(update, context):
    chat_member = update.my_chat_member.new_chat_member
    if chat_member.user.id != get_bot(context).id:
        return

    tchat = update.effective_chat
    mchat = Chat.find_by_id(tchat.id)
    if mchat is None:
        mchat = Chat(id=tchat.id)

    with mchat:
        mchat.title = tchat.title
        mchat.username = tchat.username
        mchat.type = tchat.type
        mchat.active = chat_member.status != 'left'

        # TODO: handle case where info_message_id exists but has been deleted

        if mchat.active:
            mchat.publish_info_message(context)



def handlers():
    yield ChatMemberHandler(on_member, chat_member_types=ChatMemberHandler.CHAT_MEMBER)
    yield ChatMemberHandler(on_bot_member, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER)

