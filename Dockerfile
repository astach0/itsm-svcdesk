# Lab 5: base image pinned by digest (python:3.13-slim as pulled on 2026-11-14), so a rebuild is the same image.
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

# Debian security fixes newer than the base image (apt, openssl, pcre2, zlib at the time of the pin).
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so Docker caches this layer while you edit code.
# pip is removed afterwards: svcdesk never calls it at run time, and it vendors old msgpack/urllib3/setuptools.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && pip uninstall -y pip

# Your code lives under src/ (see src/README.md). Adjust the module path in CMD to your layout.
COPY src/ /app/src/

# The SQLite file goes to /data (a named volume in docker-compose.yml), so tickets survive a restart.
RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
