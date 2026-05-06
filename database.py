# database.py
import psycopg2
from psycopg2.extras import RealDictCursor
import config
import logging

def get_db():
    """إنشاء اتصال بقاعدة البيانات باستخدام الرابط الموحد"""
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logging.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        return None
