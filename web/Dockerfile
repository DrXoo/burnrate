FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src

# `npm ci` rather than `npm install`, so the image is built from the same resolved
# versions the test runner uses locally.
RUN npm ci
RUN npm run build

FROM nginx:1.27-alpine

# openssl for the self-signed placeholder the entrypoint generates when no real
# certificate is in the shared volume yet; the nginx image links the library but
# does not ship the command.
RUN apk add --no-cache openssl

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Run by the stock nginx entrypoint, in name order, before nginx starts.
COPY docker-entrypoint.d/ /docker-entrypoint.d/
