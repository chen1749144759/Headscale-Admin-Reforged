FROM node:22-alpine AS builder

WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf \
    && addgroup -S -g 10101 scaleforge \
    && sed -i 's/^user .*/user nginx scaleforge;/' /etc/nginx/nginx.conf
COPY docker/nginx/nginx.conf /etc/nginx/templates/default.conf.template
COPY docker/nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY docker/nginx/validate-env.sh /docker-entrypoint.d/05-validate-scaleforge-env.sh
RUN chmod 0755 /docker-entrypoint.d/05-validate-scaleforge-env.sh
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
