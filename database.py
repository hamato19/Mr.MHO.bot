import os
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# الرابط الخاص بك في Neon
DB_URL = os.getenv('DATABASE_URL', "postgresql://neondb_owner:npg_blCh1ULJxyG9@ep-damp-art-a7y2e8e5-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require")

# إنشاء حوض اتصالات لضمان السرعة في الويب هوك
# ملاحظة: استخدمت DATABASE_URL كمتغير بيئة افتراضي
db_pool = pool.SimpleConnectionPool(1, 20, DB_URL)

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

def init_db():
    """تأسيس الجداول في قاعدة البيانات إذا لم تكن موجودة"""
    with get_db() as conn:
        with conn.cursor() as cur:
            # 1. جدول المستخدمين
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    secret_token TEXT UNIQUE,
                    expiry_date TIMESTAMP,
                    is_activated BOOLEAN DEFAULT FALSE
                )
            """)
            # 2. جدول الأكواد (ضروري لتوليد الأكواد)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS codes (
                    code TEXT PRIMARY KEY,
                    duration_days INTEGER NOT NULL,
                    is_used BOOLEAN DEFAULT FALSE
                )
            """)
            # 3. جدول القنوات المرتبطة
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    user_id TEXT,
                    entity_id TEXT,
                    PRIMARY KEY (user_id, entity_id)
                )
            """)
            conn.commit()
            print("✅ Database Tables Initialized Successfully")

# استدعاء التأسيس فوراً عند استيراد الملف
try:
    init_db()
except Exception as e:
    print(f"❌ Error initializing database: {e}")
