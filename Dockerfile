FROM python:3.13-slim

# Install dependencies and clean up apt cache
RUN apt-get update && \
    apt-get install -y cron curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# Copy application scripts and resources
COPY ./scripts ./scripts
COPY ./resources/*.html ./resources/

# Make sure update script (used by cron) is executable
RUN chmod +x ./scripts/update.sh
# Create cron job file in /etc/cron.d/
COPY ./scripts/my-cron /etc/cron.d/my-cron
RUN chmod 0644 /etc/cron.d/my-cron
RUN touch /var/log/my-cron.log && chmod 644 /var/log/my-cron.log

ENV PYTHONPATH=.
CMD cron -L 15 && python ./scripts/manager.py
