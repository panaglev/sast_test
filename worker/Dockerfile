FROM python:3.12

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

# sleep needs to wait for script until rabbitmq loads up
# может быть исправлено с помощью wait-for-it.sh (который настроен на пинг кролика)
CMD sleep 5 && python worker/consumer.py