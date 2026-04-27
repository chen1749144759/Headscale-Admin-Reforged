# ====== 第一阶段：构建前端 ======
FROM node:18-alpine AS builder

WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# ====== 第二阶段：Nginx 运行 ======
FROM nginx:alpine

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义配置
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/headscale-admin.conf

# 复制前端构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
