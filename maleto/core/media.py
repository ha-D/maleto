import os
import threading
from base64 import b64decode
from queue import Queue


class MediaDownloader:
    def __init__(self, bot, media_path):
        self.bot = bot
        self.media_path = media_path
        self.q = Queue()

        t = threading.Thread(target=self.download_thread)
        t.daemon = True
        t.start()

    def download_thread(self):
        while file_id := self.q.get(block=True):
            self.bot.get_file(file_id).download(os.path.join(self.media_path, file_id))


media_downloader = None


def init_media(bot, media_path=None):
    global media_downloader
    if media_path is not None:
        media_downloader = MediaDownloader(bot, media_path)


def queue_file_download(file_id):
    global media_downloader
    if media_downloader is not None:
        media_downloader.q.put(file_id)


def open_media(file_id):
    global media_downloader
    if media_downloader is not None:
        path = os.path.join(media_downloader.media_path, file_id)
        if os.path.exists(path):
            return open(path, "rb")
    return None


minion_photo = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAKQAAAEcCAMAAAB+he/fAAAABGdBTUEAALGPC/xhBQAAAAFzUkdCAK7O"
    "HOkAAAFNUExURfrmifzojfztlvfhffrkgvTeePHacvzqkgcHB1GFsBUVFPDXaUp9qUR1oTplkUBsmuLD"
    "TefKVVmPuNe2PDVdiezRX86oL928Q8ihKdKvNipMdejm4zBUgCckIt/d2yNBaPHv6tbU0hw3WjUzMWWc"
    "wExEIcGZJcrJyERDQVVUUWNjYRUtSbmPIHFwbcC+vffihwsMDHx8eg0QE+LIYQcRIayCHevSaw4gN2hN"
    "OVQ4JwgKC+HOfYeJh7S0swYICZ2dnAYICWWRrpOTkaioqHmsx9XBcFaAoJtzH9a7VQQGCYFiJNW6UgcJ"
    "DH9cS9nLjuvUb4Z9U5aSbsS4f6iWVnSgtg0ODbqoZgkKCuvVcp5rYa+mgZ+CNcCaJ8i+oPHbeL2hQt/D"
    "Ty5BWtXOuCktMdzSo8qqOrWZPfHcfaiBH43A1FtMJUNQXDtbdzVbhUdwTAvkgPAAAABvdFJOU///////"
    "//////////////////////////////////////////8P/////////////x//N/////7///9O////ff9l"
    "/////////y2T//2r//9b//////vj/8mJ///+1//g/83+/9j/rISyWP+zbZO2AK2LpSwAACAASURBVHja"
    "7Jn9TxprFscHebtZf8EYao3RaMgTlSzOCwmhMzBMIGSZgjAyKZK6ounVurEb//8f93vO8wwMim/Q3r2b"
    "vWfQ2gLOZ77n5XuGag//A6H9BfkX5P8hpGEb+BJ/akjDsx4s1/pTK2m5xoPtGY//WYhfDGnYUhdhvP5a"
    "2xXC8x4TCduzfrWSlsfpw9kt8SrjwxNGYbvvKlFt6STymRXt85r7lOtHQIbrGX9ATRoGqWHEaBeHcKln"
    "Ys8LC9C+9Yc0juFBC0ueTHjus7p4HmQz4hraL73856cbGvm2/Pk5aSyfCnL+Ta4r/rgRZHj2lO4ZSk62"
    "L+aGkbcE4wpzEq0NBENRGs90tmuvzrjKMBfQ0lNCee6C51ENRs+Y1SP1zFLmuIrjIJ3C96ZATwoCgPYM"
    "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"
)
