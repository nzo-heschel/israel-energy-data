FROM python:3.10-slim
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY ./scripts ./scripts
COPY ./resources/index.html ./resources/index.html
ENV PYTHONPATH=.
CMD python ./scripts/manager.py
