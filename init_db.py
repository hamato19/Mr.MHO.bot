# init_db.py
import logging
from database import get_db

# إعداد الـ Logging لمتابعة عملية الإنشاء
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_database():
    """إنشاء الجداول الأساسية إذا لم تكن موجودة في Neon DB"""
    
    # استعلامات إنشاء الجداول
    commands = (
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) PRIMARY KEY,
            secret_token VARCHAR(64) UNIQUE NOT NULL,
            is_activated BOOLEAN DEFAULT FALSE,
            expiry_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS entities (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
            entity_id VARCHAR(100) NOT NULL,
            entity_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, entity_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS activation_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            days INTEGER NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            used_by VARCHAR(50) REFERENCES users(user_id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    try:
        # استخدام with لفتح مدير السياق (Context Manager) بشكل صحيح
        with get_db() as conn:
            with conn.cursor() as cur:
                # تنفيذ كل أمر إنشاء جداول
                for command in commands:
                    cur.execute(command)
                
                # التأكد من وجود عمود الاسم (للمشاريع القديمة)
                cur.execute("ALTER TABLE entities ADD COLUMN IF NOT EXISTS entity_name TEXT;")
                
                conn.commit()
                logging.info("✅ تم تهيئة قاعدة البيانات بنجاح (الجداول جاهزة).")
            
    except Exception as e:
        logging.error(f"❌ خطأ أثناء تهيئة قاعدة البيانات: {e}")

if __name__ == "__main__":
    # تشغيل التهيئة عند استدعاء الملف مباشرة
    initialize_database()
