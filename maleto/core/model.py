import logging
from collections import defaultdict
from datetime import datetime
from threading import RLock

from maleto.core import sentry
from maleto.core.utils import omit
from pymongo import MongoClient

logger = logging.getLogger(__name__)

from pymongo_inmemory import MongoClient as MemMongo

db = None


def init_db(db_uri):
    global db
    if db_uri == "mem" or db_uri == "memory":
        logger.warning(
            "Using in-memory database, all data will be lost once the process exits"
        )
        client = MemMongo()
        db = client["maleto"]
    else:
        logger.debug("Connecting to DB")
        client = MongoClient(db_uri)
        client.server_info()
        db = client.get_default_database()
    logger.info("DB connected")


class Model:
    _lock = RLock()
    doc_locks = defaultdict(RLock)

    def __init__(self, **kwargs):
        self.data = kwargs

    def __getattr__(self, key):
        if key == "id":
            return self.data.get("_id", None)
        if key == "_id" or key in self.Meta.fields:
            return self.data.get(key, None)
        return super().__getattribute__(key)

    def __setattr__(self, key, val):
        if key in self.Meta.fields:
            self.data[key] = val
            return
        return super().__setattr__(key, val)

    @sentry.span
    def save(self):
        now = datetime.now()
        self.col().update_one(
            {"_id": self.id},
            {
                "$set": {**omit(self.data, "created_at"), "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def lock(self):
        self._lock.acquire()
        doc_lock = self.doc_locks[self.id]
        self._lock.release()
        doc_lock.acquire()

    def release(self):
        self._lock.acquire()
        doc_lock = self.doc_locks[self.id]
        self._lock.release()
        doc_lock.release()

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.save()
        finally:
            self.release()

    def save_to_context(self, context):
        context.user_data[self.Meta.name] = self.id

    @sentry.span
    def delete(self):
        self.col().delete_one({"_id": self.id})

    @classmethod
    def clear_context(cls, context):
        if cls.Meta.name in context.user_data:
            del context.user_data[cls.Meta.name]

    @classmethod
    def col(cls):
        return db[cls.Meta.name]

    @classmethod
    @sentry.span
    def find(cls, **kwargs):
        if "text" in kwargs:
            kwargs["$text"] = {"$search": kwargs.pop("text")}
        if "id" in kwargs:
            kwargs["_id"] = kwargs.pop("id")
        q = {k.replace("__", "."): kwargs[k] for k in kwargs}
        return [cls(**i) for i in cls.col().find(q)]

    @classmethod
    def find_one(cls, **kwargs):
        docs = cls.find(**kwargs)
        if len(docs) == 0:
            return None
        if len(docs) > 1:
            raise ModelException("More than one item found")
        return docs[0]

    @classmethod
    def find_by_id(cls, id):
        doc = cls.col().find_one({"_id": id})
        if doc is None:
            raise DoesNotExist(f"No {cls.__name__} with id {id} exists")
        return cls(**doc)

    @classmethod
    def from_context(cls, context):
        doc_id = context.user_data.get(cls.Meta.name, None)
        if not doc_id:
            raise ModelException("No item id found in context")
        return cls.find_by_id(doc_id)


class ModelException(Exception):
    pass


class DoesNotExist(ModelException):
    pass
