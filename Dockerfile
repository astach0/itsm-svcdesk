FROM python:3.13-slim

WORKDIR /app

# Dependencies first, so Docker caches this layer while you edit code.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Your code lives under src/ (see src/README.md). Adjust the module path in CMD to your layout.
COPY src/ /app/src/

# The SQLite file goes to /data (a named volume in docker-compose.yml), so tickets survive a restart.
RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
