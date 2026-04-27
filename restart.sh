#!/bin/bash
ps aux | grep start_server | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 2
cd /root/hs-admin/app
nohup python3 start_server.py > /var/log/hs-admin.log 2>&1 &
sleep 3
echo "=== listening ==="
ss -tlnp | grep 5175
echo "=== log ==="
tail -5 /var/log/hs-admin.log
