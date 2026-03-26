ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY run.sh .
RUN chmod +x /app/run.sh
COPY src/ ./src/

EXPOSE 8099
CMD ["/bin/bash", "/app/run.sh"]
