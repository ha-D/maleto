FROM python:3.8

WORKDIR /bot
COPY . .

RUN pip install -r requirements.txt
ENTRYPOINT python -m maleto