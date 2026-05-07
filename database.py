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
        # اختيارياً: يمكنك جعل كل العمليات تعيد RealDictCursor تلقائياً
        yield conn
    except Exception as e:
        logging.error(f"❌ خطأ في قاعدة البيانات: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            if not conn.closed:
                conn.close()

def init_db():
    """دالة اختيارية للتأكد من هيكلة الجداول عند بدء التشغيل"""
    with get_db() as conn:
        with conn.cursor() as cur:
            # التأكد من وجود الجداول الأساسية
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_name TEXT,
                    UNIQUE(user_id, entity_id)
                );
            """)
            conn.commit()
