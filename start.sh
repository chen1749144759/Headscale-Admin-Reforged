#!/bin/bash
cd /root/hs-admin/app
nohup python3 start_server.py >> /var/log/hs-admin.log 2>&1 &
sleep 5
echo "=== process ==="
ps aux | grep start_server | grep -v grep
echo "=== port ==="
ss -tlnp | grep 5175
echo "=== log ==="
tail -10 /var/log/hs-admin.log
