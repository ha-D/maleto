import logging

from telegram import *

from .models import Model

logger = logging.getLogger(__name__)


class Chat(Model):
    class Meta:
        name = 'chats'
        fields = ('id', 'title', 'username', 'type', 'info_message_id', 'active')

    def publish_info_message(self, context):
        if self.info_message_id is None:
            info_msg = context.bot.send_message(chat_id=self.id, text=self.generate_info_message(), parse_mode=ParseMode.MARKDOWN)
            self.info_message_id = info_msg.message_id
            info_msg.pin(disable_notification=True)
        else:
            context.bot.edit_message_text(chat_id=self.id, message_id=self.info_message_id, text=self.generate_info_message(), parse_mode=ParseMode.MARKDOWN)

    
    def generate_info_message(self):
        from .item import Item
        
        items = Item.find(posts__chat_id=self.id)
        s =  '\n'.join([
            'Welcome!!',
            '',
            'These items are currently on sale:',
            *[item.chat_link(self.id) for item in items],
            '',
        ])
        return s

