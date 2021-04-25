import logging
from telegram.ext import *
from telegram import *
from telegram.utils.helpers import *

from .chat import Chat
from .user import User

logger = logging.getLogger(__name__)

STATUS_MEMBER = ["member", "creator", "administrator"]
STATUS_ADMIN = ["creator", "administrator"]


def on_member_status_change(update, context):
    cmu = update.chat_member
    cm = cmu.new_chat_member
    chat = Chat.create_or_update_from_api(context, cmu.chat)
    user = User.create_or_update_from_api(cm.user, lang=chat.lang)
        
    with user:
        with chat:
            if user.lang == None and chat.lang is not None:
                user.lang = chat.lang

            if cm.status in STATUS_MEMBER:
                handle_user_join(user, chat)
            else:
                handle_user_leave(user, chat)
            if cm.status in STATUS_ADMIN:
                handle_admin_join(user, chat)
            else:
                handle_admin_leave(user, chat)


def on_bot_status_change(update, context):
    """ Called when bot leaves or enters grpup """
    cmu = update.my_chat_member
    cm = cmu.new_chat_member

    # if cm.status not in STATUS_ADMIN or cm.user.id != get_bot(context).id:
    #     return
    chat = Chat.create_or_update_from_api(context, cmu.chat)

    if cm.status in STATUS_MEMBER:
        api_admins = context.bot.get_chat_administrators(chat.id)
        admins = [User.create_or_update_from_api(adm.user, lang=chat.lang) for adm in api_admins if not adm.user.is_bot]
        # TODO: concurrency problems on updating users here
        with chat:
            chat.active = True
            if cm.status in STATUS_MEMBER:
                for adm in admins:
                    handle_user_join(adm, chat)
                    adm.save()
                    handle_admin_join(adm, chat)
    else:
        chat.active = False
        chat.save()


def handle_user_join(user, chat):
    exists = any(c == chat.id for c in user.chats)
    if not exists:
        logger.info(f'User joined chat. user:{user.id} chat:{chat.id}')
        user.chats.append(chat.id)


def handle_user_leave(user, chat):
    exists = any(c == chat.id for c in user.chats)
    if exists:
        logger.info(f'User left chat. user:{user.id} chat:{chat.id}')
        user.chats = [c for c in user.chats if c != chat.id]


def handle_admin_join(user, chat):
    exists = any(u == user.id for u in chat.admins)
    if not exists:
        logger.info(f'User is now chat admin. user:{user.id} chat:{chat.id}')
        chat.admins.append(user.id)


def handle_admin_leave(user, chat):
    exists = any(u == user.id for u in chat.admins)
    if exists:
        logger.info(f'User is no longer chat admin. user:{user.id} chat:{chat.id}')
        chat.admins = [u for u in chat.admins if u != user.id]


def handlers():
    yield ChatMemberHandler(
        on_member_status_change, chat_member_types=ChatMemberHandler.CHAT_MEMBER
    )
    yield ChatMemberHandler(
        on_bot_status_change, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER
    )
