ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12
FROM $BUILD_FROM

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.sh .
COPY src/ ./src/

EXPOSE 8099
CMD ["/bin/bash", "/app/run.sh"]
