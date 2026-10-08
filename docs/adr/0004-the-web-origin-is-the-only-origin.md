# The Web UI's origin is the only origin, via the nginx in its own container

The browser used to load the SPA from the `web` container and then call the
backend on `:8000` at whatever host or IP it had guessed, so every origin the app
might be reached on had to be enumerated in `APP_CORS_ORIGINS` and changing the
VM's address broke it. `web/nginx.conf` now proxies `/api/v1/` and
`/enable_banking_items/` to the backend, so the browser only ever talks to the
origin it loaded the page from, nothing is cross-origin, and CORS leaves the
request path entirely. `detectApiBase` probes same-origin first instead of last
for the same reason.

This file was found uncommitted in the working tree, dated 3 August, and already
live: `nginx.conf` is `COPY`ed into the image at build time, so the running
container had been built from a file git did not have, and a rebuild from a clean
checkout would have produced a different deployment from the one in use. It is
recorded here because nothing in the code says why the backend's CORS
configuration is nearly inert.

## Considered Options

**Enumerating origins and calling the backend port directly** is what shipped
before, and it is the arrangement a reader would assume from `APP_CORS_ORIGINS`
still existing. Rejected: the set of origins is a function of how the host
happens to be addressed, which is not knowable at build time and changes without
the app changing.

**Leaving the bank callback unproxied** was not viable rather than rejected.
`ENABLE_BANKING_REDIRECT_URL` points at the public hostname rather than the
backend port, so without `/enable_banking_items/` proxied the provider's callback
fell through to the SPA's `index.html` instead of reaching the handler.

## Consequences

**`--forwarded-allow-ips "*"` on uvicorn is only safe because nginx overwrites
`X-Forwarded-For`.** The header is set from `$remote_addr`, not
`$proxy_add_x_forwarded_for`, which appends to whatever the client sent — and
uvicorn's always-trust branch reads the leftmost entry. With the appending form,
`request.client.host` was whatever the request asked for, and both the login
lockout and the Enable Banking rate limiter key on it, so anyone able to reach
the published port had unlimited password guesses and unlimited bank syncs. The
overwrite and the backend's loopback bind are each load-bearing and cover
different attacks: the bind stops the proxy being bypassed, the overwrite stops
spoofing through it. Putting another proxy in front of nginx would require that
proxy's forwarded address to be trusted here explicitly, not this header appended
to.

**The security headers are set at server level and the upstream's copies are
hidden.** `add_header` appends rather than replaces, so the backend's own four
headers arrived twice on every proxied response — and two
`Cross-Origin-Opener-Policy` values do not parse as a structured field, which
degrades the policy to `unsafe-none`. Scoping `add_header` to `location /`
instead would leave nginx's own responses bare, because a 502 from a stopped
backend or a 504 from the read timeout never reaches the backend middleware.

**`proxy_read_timeout` is raised to 300s because the sync pages serially.** An
Enable Banking sync routinely runs past nginx's 60s default, which returned a 504
while the import went on to commit: the owner saw a failure and retried a sync
that had worked, burning the rate-limit bucket.

**The file is pinned to Docker Compose.** `proxy_pass` goes through a
`$burnrate_backend` variable so Docker's embedded resolver is consulted per
request and a backend restart on a new IP is picked up within 10s rather than
cached for the lifetime of the nginx process. The cost is that a variable
`proxy_pass` requires a `resolver`, so on any runtime without `127.0.0.11` every
proxied request fails. Moving off Compose means revisiting this line.
