"""
Headscale-Admin-Pro 生产级启动入口
使用 Waitress 多线程 WSGI 服务器
"""
import os
from waitress import serve
from app import app

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    threads = int(os.environ.get('THREADS', 8))
    
    print(f' Headscale Admin Pro 启动中...')
    print(f'   地址: http://{host}:{port}')
    print(f'   线程: {threads}')
    print(f'   调试: {os.environ.get("FLASK_DEBUG", "False")}')
    
    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        channel_timeout=120,
        url_scheme='http'
    )
