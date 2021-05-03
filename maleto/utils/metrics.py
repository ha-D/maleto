from prometheus_client import Counter, start_http_server


def init_monitoring(metrics_port):
    if metrics_port:
        start_http_server(metrics_port)


item_create_start = Counter(
    "maleto_item_create_start", "Item creations which have been started"
)
item_create_done = Counter(
    "maleto_item_create_done", "Item creations which have been finished"
)
item_create_cancel = Counter(
    "maleto_item_create_cancel", "Item creations which have been cancelled"
)
item_create_no_photo = Counter(
    "maleto_item_create_no_photo", "User tried to continue without sending photos"
)
item_bid_add = Counter("maleto_item_bid_add", "Bid added")
item_bid_remove = Counter("maleto_item_bid_remove", "Bid removed")
item_buyer_change = Counter(
    "maleto_item_buyer_change",
    "Winning bidder changes (only if changed to and from a user not null)",
)

user_create = Counter("maleto_user_create", "Users created")
user_join_chat = Counter(
    "maleto_user_join_chat", "Users that have joined the channels/groups"
)
user_leave_chat = Counter(
    "maleto_user_leave_chat", "Users that have left the channels/groups"
)

chat_create = Counter("maleto_chat_create", "Chats created")

transaction_success = Counter("maleto_error", "Unhanlded errors occurred")
transaction_error= Counter("maleto_error", "Unhanlded errors occurred")


