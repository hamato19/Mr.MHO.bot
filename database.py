# database.py
import psycopg2
from psycopg2.extras import RealDictCursor
import config
import logging
from contextlib import contextmanager

@contextmanager
def get_db():
    """إنشاء اتصال بقاعدة البيانات مع ضمان الإغلاق التلقائي"""
    conn = None
    try:
        # الاتصال باستخدام رابط Neon المخزن في config
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        yield conn
    except Exception as e:
        logging.error(f"❌ خطأ في قاعدة البيانات: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()
