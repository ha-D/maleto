from pymongo import MongoClient
from bson.objectid import ObjectId
from collections import defaultdict
from threading import Lock, RLock
from telegram.ext import *
from telegram.error import BadRequest
from telegram import *
from utils import cb_data, find_by
import logging

logger = logging.getLogger(__name__)


client = MongoClient()
db = client['maleto']
db.items.create_index([('title', 'text'), ('description', 'text')])


class Model:
    _lock = RLock()
    doc_locks = defaultdict(RLock)
    mongo_id = True

    def __init__(self, **kwargs):
        self.data = kwargs
    
    def __getattr__(self, key):
        if self.mongo_id and key == 'id':
            return self.data.get('_id', None)
        if key == '_id' or key in self.Meta.fields:
            return self.data.get(key, None)
        return super().__getattribute__(key)

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
        try:
            doc_lock.release()
        except RuntimeError:
            # in case wasn't locked because it had no id
            pass
        
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
