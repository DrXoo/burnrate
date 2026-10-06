FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml ./pyproject.toml
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

# --proxy-headers with a wildcard trust list is safe only because the published
# port is bound to 127.0.0.1 (docker-compose.yml): the sole route in from off
# the host is nginx, so X-Forwarded-For cannot be spoofed to defeat the login
# lockout or the bank rate limit, both of which key on the client address.
CMD ["uvicorn", "burnrate.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]

