#!/bin/bash
# Headscale Admin Pro - 部署启动脚本
# 前后端分离模式：后端 API (uvicorn :5175) + 前端 (nginx 或直接访问 dist)

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$PROJECT_DIR/api"
WEB_DIR="$PROJECT_DIR/web"

echo "=== Headscale Admin Pro 部署 ==="
echo "项目目录: $PROJECT_DIR"

# 启动后端 API
echo ""
echo "--- 启动后端 API ---"
cd "$API_DIR"
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 5175 --workers 2 --log-level info >> /var/log/hs-admin-api.log 2>&1 &
API_PID=$!
echo "API 启动成功，PID: $API_PID，端口: 5175"

sleep 2
echo ""
echo "=== 启动验证 ==="
echo "API 进程:"
ps aux | grep "uvicorn" | grep -v grep || echo "  (未找到)"
echo ""
echo "API 端口:"
ss -tlnp | grep 5175 || echo "  (未监听)"
echo ""
echo "=== 部署完成 ==="
echo ""
echo "前端开发模式: cd $WEB_DIR && npm run dev"
echo "前端构建: cd $WEB_DIR && npm run build"
echo "前端构建产物在 $WEB_DIR/dist，可用 nginx 或其他 Web 服务器部署"
echo ""
echo "推荐 Nginx 配置:"
echo "  前端静态文件: root $WEB_DIR/dist"
echo "  API 反向代理: proxy_pass http://127.0.0.1:5175"
