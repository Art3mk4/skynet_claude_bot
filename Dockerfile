FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-test.txt

COPY . .

# Делаем entrypoint исполняемым
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
