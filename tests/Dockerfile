# ai-generated: 100% - generated as the Lab 2 Stretch 3 pytest runner
FROM python:3.13-slim
WORKDIR /tests
RUN pip install --no-cache-dir pytest
COPY tests/ /tests/
COPY fixtures/ /fixtures/
ENV PYTHONUNBUFFERED=1
CMD ["python", "/tests/run_tests.py"]
