#!/bin/bash
# 修复 headscale 数据库权限
PGPASSWORD="HsAdmin@2026PG" psql -h 127.0.0.1 -p 15432 -U headscale_admin -d headscale_admin -c "
DO \$\$
DECLARE
    t RECORD;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
        EXECUTE 'ALTER TABLE ' || t.tablename || ' OWNER TO headscale_admin';
    END LOOP;
END \$\$;
"
