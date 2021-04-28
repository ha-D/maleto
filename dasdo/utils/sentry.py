from collections import defaultdict
import logging

import sentry_sdk

logger = logging.getLogger(__name__)
sentry_enabled = False
seen_events = defaultdict(lambda: 0)
duplicate_event_limit = 100


def init_sentry(dsn):
    global sentry_enabled
    if dsn:
        logger.debug("Initializing sentry")
        sentry_enabled = True
        sentry_sdk.init(dsn, traces_sample_rate=1.0, before_send=filter_event)


def if_sentry_enabled(f):
    def inner(*args, **kwargs):
        global sentry_enabled
        if sentry_enabled:
            return f(*args, **kwargs)

    return inner


@if_sentry_enabled
def on_error(update, context):
    sentry_sdk.capture_exception(context.error)


def filter_event(event, hint):
    try:
        e = event["exception"]["values"][0]
        k = f"{e['type']}#{e['value']}".__hash__()
        seen_events[k] += 1
        if seen_events[k] > duplicate_event_limit:
            return None
    except (KeyError, IndexError):
        pass
    return event