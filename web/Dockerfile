FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json tsconfig.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src

# `npm ci` rather than `npm install`, so the image is built from the same resolved
# versions the test runner uses locally.
RUN npm ci
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
