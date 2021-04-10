from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
from threading import Lock
from telegram.ext import *
from telegram.error import BadRequest
from telegram import *
import callbacks as cb
from utils import cb_data, find_by
import logging

logger = logging.getLogger(__name__)


client = MongoClient()
db = client['maleto']
db.items.create_index([('title', 'text'), ('description', 'text')])


class Model:
    _lock = Lock()
    doc_locks = defaultdict(Lock)
    mongo_id = True

    def __init__(self, **kwargs):
        self.data = kwargs
    
    def __getattr__(self, key):
        if self.mongo_id and key == 'id':
            return self.data.get('_id', None)
        if key == '_id' or key in self.Meta.fields:
            return self.data.get(key, None)
        return super().__getattr__(key) # TODO: this is apparently wrong

    def __setattr__(self, key, val):
        if key in self.Meta.fields:
            self.data[key] = val
            return
        return super().__setattr__(key, val)

    def save(self):
        id = self._id
        if id:
            self.col().update({'_id': id}, self.data)
        else:
            self.id = self.col().insert(self.data)

    def lock(self):
        if not self.id:
            return
        self._lock.acquire()
        doc_lock = self.doc_locks[self.id]
        self._lock.release()
        doc_lock.acquire()

    def release(self):
        if not self.id:
            return
        self._lock.acquire()
        doc_lock = self.doc_locks[self.id]
        self._lock.release()
        if doc_lock.locked():
            doc_lock.release()
        
    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.save()
        self.release()

    def save_to_context(self, context):
        context.user_data[self.Meta.name] = self.id

    def delete(self):
        self.col().delete_one({'_id': self._id})

    @classmethod
    def clear_context(cls, context):
        if cls.Meta.name in context.user_data:
            del context.user_data[cls.Meta.name]

    @classmethod
    def col(cls):
        return db[cls.Meta.name]

    @classmethod
    def find(cls, **kwargs):
        if 'text' in kwargs:
            kwargs['$text'] = {'$search': kwargs.pop('text')}
        if cls.mongo_id and 'id' in kwargs:
            kwargs['_id'] = kwargs.pop('id')
        if '_id' in kwargs:
            kwargs['_id'] = ObjectId(kwargs['_id'])
        q = {k.replace('__', '.'): kwargs[k] for k in kwargs}
        return [cls(**i) for i in cls.col().find(q)]

    @classmethod
    def find_one(cls, **kwargs):
        docs = cls.find(**kwargs)
        if len(docs) == 0:
            raise ValueError('No items found')
        if len(docs) > 1:
            raise ValueError('More than one item found')
        return docs[0]

    @classmethod
    def find_by_id(cls, id):
        if cls.mongo_id:
            doc = cls.col().find_one({'_id': ObjectId(id)})
        else:
            doc = cls.col().find_one({'id': id})
        if doc is None:
            return None
        return cls(**doc)

    @classmethod
    def from_context(cls, context):
        doc_id = context.user_data.get(cls.Meta.name, None)
        if not doc_id:
            raise ValueError('No item id found in context')
        return cls.find_by_id(doc_id)


class Chat(Model):
    mongo_id = False

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
        items = Item.find(posts__chat_id=self.id)
        return '\n'.join([
            'Welcome!!',
            '',
            'These items are currently on sale:',
            *[item.link() for item in items],
            '',
        ])


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
            name = f'{self.first_name or ""} {self.last_name or ""}''
        return f'[@{name}](tg://user?id={self.id})'

    
class Item(Model):
    class Meta:
        name = 'items'
        fields = ('active', 'title', 'description', 'owner_id', 'photos', 
                'published_messages', 'bids', 'base_price', 
                'interaction_messages', 'posts', 'min_price_inc')


    def __init__(self, **kwargs):
        super().__init__(**{'photos': [], 'bids': [], 'interaction_messages': [], 
        'posts': [], 'stores': [], **kwargs})

    @classmethod
    def find(cls, **kwargs):
        return super().find(active=True, **kwargs)

    @property
    def owner(self):
        return User.find_by_id(self.owner_id)

    def get_latest_bids(self, user_id=None):
        """ 
        Returns (price, place_in_queue, total_queue_size)
        """
        if len(self.bids) == 0:
            return self.base_price, -1, 0
        latest = self.bids[-1]
        price = latest['price']
        bids = latest['users']
        try:
            return price, bids.index(user_id), len(bids)
        except ValueError:
            return price, -1, len(bids)
    
    def remove_user_from_bids(self, user_id):
        for bid in self.bids:
            bid['users'] = [u for u in bid['users'] if u != user_id]
        self.bids = [b for b in self.bids if len(b['users']) > 0]

    def add_user_bid(self, user_id, price):
        highest_price, place_in_queue, total_queue_size = self.get_latest_bids(user_id)
        if price < highest_price:
            raise ValueError('price low')
        if price == highest_price and place_in_queue >= 0:
            raise ValueError('already in queue')

        self.remove_user_from_bids(user_id)

        # if no bids or bidding with higher price
        if total_queue_size == 0 or highest_price < price:
            self.bids.append({'price': price, 'users': [user_id]})
        else:
            self.bids[-1]['users'].append(user_id)
    
    def add_sale_message(self, context, chat_id):
        post, _ = find_by(self.posts, 'chat_id', chat_id)
        if not post:
            media = [InputMediaPhoto(media=photo) for photo in self.photos]
            media[0].caption = self.generate_sale_message()
            media[0].parse_mode = parse_mode=ParseMode.MARKDOWN
            messages = context.bot.send_media_group(chat_id=chat_id, media=media)
            self.posts.append({'chat_id': chat_id, 'messages': [m.message_id for m in messages]})
        # Need to save for the chat publish to work
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    def remove_sale_message(self, context, chat_id):
        post, idx = find_by(self.posts, 'chat_id', chat_id)
        if post:
            for message_id in post['messages']:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            del self.posts[idx]
        self.save()
        Chat.find_by_id(chat_id).publish_info_message(context)

    def publish_to_messages(self, context):
        sale_message = self.generate_sale_message()
        for post in self.posts:
            chat_id = post['chat_id']
            message_id = post['messages'][0]
            ignore_no_changes(context.bot.edit_message_caption, chat_id=int(chat_id),
                message_id=message_id, parse_mode=ParseMode.MARKDOWN_V2, caption=sale_message)

        for imes in self.interaction_messages:
            self.publish_to_interaction_message(context, imes)

    def change_user_interaction_message(self, context, user_id, message_id):
        imes, _ = find_by(self.interaction_messages, 'user_id', user_id)
        if imes is not None:
            try:
                context.bot.edit_message_caption(chat_id=imes['user_id'], message_id=imes['message_id'], caption=f'{self.title}', reply_markup=InlineKeyboardMarkup([]))
            except BadRequest as e:
                pass
            imes['message_id'] = message_id
        else:
            self.interaction_messages.append({'user_id': user_id, 'message_id': message_id})

    def change_interaction_message_state(self, user_id, state):
        imes, _ = find_by(self.interaction_messages, 'user_id', user_id)
        imes['state'] = state

    def publish_to_interaction_message_for_user(self, context, user_id):
        imes, _ = find_by(self.interaction_messages, 'user_id', user_id)
        self.publish_to_interaction_message(context, imes)

    def delete_all_messages(self, context):
        for imes in self.interaction_messages:
            try:
                msg = '\n'.join([
                    self.title,
                    '',
                    'This item is no longer available'
                ])
                context.bot.edit_message_caption(chat_id=imes['user_id'], message_id=imes['message_id'], caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([]))
            except BadRequest as e:
                logger.warning('Unable to disable interaction message (%d, %d)', imes['chat_id'], imes['message_id'], exc_info=True)

        for post in self.posts:
            chat_id = post['chat_id']
            for message_id in post['messages']:
                try:
                    context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                except BadRequest as e:
                    logger.warning('Unable to delete post message (%d, %d)', chat_id, message_id, exc_info=True)

    def publish_to_interaction_message(self, context, imes):
        user_id = imes['user_id']
        price, pos_in_queue, total_queue_size = self.get_latest_bids(user_id)
        if user_id == self.owner_id:
            state = imes.get('state', 'default')
            msg = self.generate_owner_message()
            if state == 'default':
                reply_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Publish", callback_data=cb_data(cb.PUBLISH_TO_STORE, self.id))
                    ],
                    [
                        InlineKeyboardButton("🗑  Delete", callback_data=cb_data(cb.DELETE_ITEM, self.id)),
                        InlineKeyboardButton("✏️  Edit", callback_data=cb_data(cb.EDIT_ITEM, self.id)),
                    ]
                ])
            elif state == 'publishing':
                user = User.find_one(id=user_id)
                existing = set([s['chat_id'] for s in self.posts])
                buttons = [InlineKeyboardButton("◀️ Back", callback_data=cb_data(cb.PUBLISH_TO_STORE, self.id, 'cancel'))]
                for chat in user.chats: 
                    if chat['chat_id'] in existing:
                        action = 'rem'
                        btn_msg = f'Remove from {chat["name"]}'
                    else:
                        action = 'add'
                        btn_msg = f'Publish to {chat["name"]}'
                    buttons.append(InlineKeyboardButton(btn_msg, callback_data=cb_data(cb.PUBLISH_TO_STORE, self.id, action, chat['chat_id'])))
                reply_markup = InlineKeyboardMarkup([[b] for b in buttons])
                # reply_markup = InlineKeyboardMarkup(list(zip(buttons[::2], buttons[1::2])))
            elif state == 'deleting':
                msg = '\n'.join([
                    msg,
                    'Are you sure you want to delete this item? 🙀'
                ])
                reply_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Yes", callback_data=cb_data(cb.DELETE_ITEM, self.id, 'yes')),
                    InlineKeyboardButton("No", callback_data=cb_data(cb.DELETE_ITEM, self.id, 'no')),
                ]])
        elif pos_in_queue == 0:
            msg = f'You are the current buyer with {price}',
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("I don't want it anymore", callback_data=cb_data(cb.REVOKE, self.id))]])
        elif pos_in_queue > 0:
            msg =f'You are {pos_in_queue}th person in queue for price {price}'
            reply_markup = InlineKeyboardMarkup([
                [   
                    InlineKeyboardButton("Make Higher Offer", callback_data=cb_data(cb.BID, self.id)),
                    InlineKeyboardButton("I don't want it anymore", callback_data=cb_data(cb.REVOKE, self.id)),
                ],
            ])
        elif total_queue_size == 0:
            msg = f'No ones buying, the price is {price} you want it?'
            reply_markup = InlineKeyboardMarkup([
                [   
                    InlineKeyboardButton("Buy with this price", callback_data=cb_data(cb.BID_SAME, self.id, price)),
                    InlineKeyboardButton("Make Higher Offer", callback_data=cb_data(cb.BID, self.id)),
                ],
            ])
        else:
            msg = f'There are {total_queue_size} people buying with price {price}, you want it'
            reply_markup = InlineKeyboardMarkup([
                [   
                    InlineKeyboardButton("Go in queue with this price", callback_data=cb_data(cb.BID_SAME, self.id, price)),
                    InlineKeyboardButton("Make Higher Offer", callback_data=cb_data(cb.BID, self.id)),
                ],
            ])
        ignore_no_changes(context.bot.edit_message_caption, chat_id=imes['user_id'], message_id=imes['message_id'], caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

    def generate_sale_message(self):
        price, idx, q_len = self.get_latest_bids()
        msg = [
            f'*{self.title}*',
            f'Seller: {self.owner.link()}',
            '',
            self.description,
            '',
            f'Price: {price}',
        ]

        if q_len > 0:
            users = [User.find_by_id(uid) for uid in self.bids[-1]['users']]
            msg += [f'Buyer: {users[0].link()}']
            if len(users) > 1:
                users = users[1:]
                msg.append('Waiting List:')
                if len(users) <= 4:
                    msg += [f'{i+1}. {u.link()}' for i, u in enumerate(users)]
                elif len(users) > 4:
                    msg += [f'{i+1}. {u.link()}' for i, u in enumerate(users[:3])]
                    msg.append(f'_{len(users) - 3} more people..._')

        msg += [
            '',
            f'[Click here to buy this item](https://t.me/maltobot?start={self.id})'
        ]

        return  '\n'.join(msg)

    def generate_owner_message(self):
        highest_price, _, total_queue_size = self.get_latest_bids()

        return '\n'.join([
            self.title,
            '',
            f'Published in *{len(self.posts)}* chats',
            '',
            f'Starting Price: {self.base_price}',
            f'Current Bid:    {highest_price} - {total_queue_size} people in queue',
            '',
        ])

    def link(self):
        return f'[{self.title}](https://t.me/maltobot?start=item-{self.id})'

def ignore_no_changes(f, **kwargs):
    try:
        f(**kwargs)
    except BadRequest as e:
        if 'is not modified' not in e.message:
            raise
        print('Warning: no changes!')