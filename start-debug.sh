#!/bin/bash
cd /opt/headscale-admin
echo "Starting service..."
python3 -c "
import sys
sys.path.insert(0, '.')
from api.main import app
print('Import successful!')
print('Static dir check...')
import os
api_dir = os.path.dirname(os.path.abspath('api/main.py'))
project_dir = os.path.dirname(api_dir)
static_dir = os.path.join(project_dir, 'static')
print(f'Static dir: {static_dir}')
print(f'Exists: {os.path.exists(static_dir)}')
" 2>&1
echo "---"
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 5175 --log-level info
