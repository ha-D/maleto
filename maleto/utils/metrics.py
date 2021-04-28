from prometheus_client import Counter, start_http_server

def init_monitoring(args):
    if args.metrics_port:
        start_http_server(args.metrics_port)

item_create_start = Counter('item_create_start', 'Item creations which have been started')
item_create_done = Counter('item_create_done', 'Item creations which have been finished')
item_create_cancel = Counter('item_create_cancel', 'Item creations which have been cancelled')
item_create_no_photo = Counter('item_create_no_photo', 'User tried to continue without sending photos')