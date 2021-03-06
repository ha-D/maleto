# Maleto Bot

A bot for selling or auctioning used items on Telegram.

#### Built With
- [python-telegram-bot](python-telegram-bot)

## Installation

#### Using pip


```bash
pip install maleto
```

#### Manual Install
Maleto uses `poetry` for package management. Learn how to install poetry [here](https://python-poetry.org/docs/).

```
git clone https://github.com/ha-D/maleto
cd maleto
poetry install
poetry run maleto
```

## Prerequisites
#### Telegram Bot API Token
A Telegram API token is needed in order to run maleto. You can easily obtain one by opening [BotFather](https://t.me/botfather) in your Telegram client, entering `/newbot` and just following the steps. Learn more about Telegram Bots [here](https://core.telegram.org/bots).

#### MongoDB
Maleto persists its data in a MongoDB. You will need to provide a URI to a MongoDB database when running maleto.

You can also choose to run with an _in-memory_ MongoDB instance and Maleto will download and spin-up an in-memory MongoDB instance using [pymongo_inmemory](https://github.com/kaizendorks/pymongo_inmemory). Note however, if you use this mode all your data will be lost once the process exits.

## Running the Bot

Use the following command to run maleto in _poll_ mode using your API token.
```bash
maleto start -t [API_TOKEN] -m poll
```

If you don't have a MongoDB instance running on your local machine you will need to specify a MongoDB URI as well.
```bash
maleto start -t [API_TOKEN] -m poll -d mongodb://1.2.3.4/maleto
```

Or use `mem` instead to use an in-memory database
```bash
maleto start -t [API_TOKEN] -m poll -d mem
```

### Poll vs Webhook
Like most Telegram Bots, maleto can be configured to receive updates using either [polling or webhooks](https://core.telegram.org/bots/api#getting-updates). Polling is slower but useful for testing since it doesn't require a valid domain name or HTTPS server.



## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.


## License
[MIT](https://choosealicense.com/licenses/mit/)