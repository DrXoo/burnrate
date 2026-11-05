#!/bin/sh
# Reload nginx daily so a renewed certificate is actually served.
#
# nginx reads the certificate once, at startup. acme.sh renews into the shared
# volume roughly every 60 days without touching this container, so without a reload
# nginx would keep serving the old pair until something restarted it -- and would
# serve an *expired* one from day 90, silently, which is the shape of failure this
# project least wants: the site breaks for the one hostname the bank redirects to,
# and nothing says why.
#
# A daily reload is graceful (workers finish their requests) and costs nothing, so
# it is preferred over wiring this container to the Docker socket to be told.
set -eu

(
    while true; do
        sleep 86400
        nginx -s reload 2>/dev/null || true
    done
) &
