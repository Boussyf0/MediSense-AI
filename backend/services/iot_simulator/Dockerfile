FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir aiokafka==0.11.0

COPY main.py ./main.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
