# -*- coding:utf-8 -*-
"""
数据库上下文管理器
同时支持 SQLite（本地开发）和 PostgreSQL（生产部署）
通过 config_loader 中的 DATABASE_URI 自动判断
"""
import sqlite3
import traceback
import config_loader

# 从配置读取数据库 URI
DATABASE = config_loader.DATABASE_URI

# 判断数据库类型
IS_POSTGRES = DATABASE and DATABASE.startswith("postgresql://")


# ---------- PostgreSQL 上下文管理器 ----------
if IS_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        PSYCOPG2_AVAILABLE = True
    except ImportError:
        PSYCOPG2_AVAILABLE = False

    class PostgresDB(object):
        def __init__(self, database=DATABASE, ignore_exc=False):
            self.database = database
            self.ignore_exc = ignore_exc
            self.connection = None
            self.cursor = None

        def __enter__(self):
            try:
                self.connection = psycopg2.connect(self.database)
                # 使用字典游标，兼容 sqlite3.Row 的访问方式
                self.cursor = self.connection.cursor(
                    cursor_factory=psycopg2.extras.DictCursor
                )
                return self.cursor
            except Exception as ex:
                traceback.print_exc()
                raise ex

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type is not None:
                    self.connection.rollback()
                    return self.ignore_exc
                else:
                    self.connection.commit()
            except Exception as ex:
                traceback.print_exc()
                raise ex
            finally:
                if self.cursor:
                    self.cursor.close()
                if self.connection:
                    self.connection.close()

    # 别名：让业务代码统一用 DB()
    DB = PostgresDB
    # 兼容性：确保旧代码 from exts import SqliteDB 也能工作
    SqliteDB = PostgresDB
else:
    # ---------- SQLite 上下文管理器 ----------
    class SqliteDB(object):
        def __init__(self, database=DATABASE, isolation_level='', ignore_exc=False):
            self.database = database
            self.isolation_level = isolation_level
            self.ignore_exc = ignore_exc
            self.connection = None
            self.cursor = None

        def __enter__(self):
            try:
                self.connection = sqlite3.connect(
                    database=self.database, isolation_level=self.isolation_level
                )
                self.cursor = self.connection.cursor()
                self.cursor.row_factory = sqlite3.Row  # 返回类似字典的对象
                # 开启外键约束
                self.cursor.execute("PRAGMA foreign_keys = ON;")
                return self.cursor
            except Exception as ex:
                traceback.print_exc()
                raise ex

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type is not None:
                    self.connection.rollback()
                    return self.ignore_exc
                else:
                    self.connection.commit()
            except Exception as ex:
                traceback.print_exc()
                raise ex
            finally:
                if self.cursor:
                    self.cursor.close()
                if self.connection:
                    self.connection.close()

    # 别名
    DB = SqliteDB
    # 兼容性
    PostgresDB = SqliteDB
