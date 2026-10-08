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

# --proxy-headers with a wildcard trust list trusts the *leftmost* X-Forwarded-For
# entry, so it is only as trustworthy as the hop that sets that header. Two things
# make it safe here, and both are load-bearing: the published port is bound to
# 127.0.0.1 (docker-compose.yml), so nginx is the sole route in from off the host;
# and nginx *overwrites* X-Forwarded-For with $remote_addr (web/nginx.conf) rather
# than appending to it, so a client cannot inject an address of its own. Without the
# overwrite the loopback bind alone does not help: the spoofed header travels
# through the proxy, and the login lockout and bank rate limit both key on the
# resulting address. Narrowing this to nginx's own address instead would be the
# belt-and-braces version, but its compose-assigned IP is not stable.
CMD ["uvicorn", "burnrate.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]

