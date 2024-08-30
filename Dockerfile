FROM python:3.11-slim
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
RUN apt-get update
RUN apt-get -y install cron
RUN apt-get -y install curl
COPY ./scripts ./scripts
COPY ./resources/*.html ./resources/
RUN chmod 777 ./scripts/update.sh
RUN crontab -l | { cat; echo "0 1 * * * /scripts/update.sh"; } | crontab -
ENV PYTHONPATH=.
CMD cron && python ./scripts/manager.py
