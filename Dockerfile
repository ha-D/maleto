FROM python:3.8

WORKDIR /bot
COPY ./requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT python -m maleto