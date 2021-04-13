import logging

from models import Model

logger = logging.getLogger(__name__)


class User(Model):
    mongo_id = False

    class Meta:
        name = 'users'
        fields = ('id', 'username', 'first_name', 'last_name', 'chats')

    def __init__(self, **kwargs):
        super().__init__(**{'chats': [], **kwargs})

    @classmethod
    def update_from_request(cls, update):
        user = update.effective_user
        if user is not None:
            cls.col().update_one(
                {'id': user.id},
                {'$set': {'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}},
                upsert=True
            )

    def link(self):
        name = self.username
        if not name:
            name = f'{self.first_name or ""} {self.last_name or ""}'
        return f'[@{name}](tg://user?id={self.id})'

    
