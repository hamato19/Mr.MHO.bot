# init_db.py
import logging
from database import get_db

# إعداد الـ Logging لمتابعة عملية الإنشاء
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_database():
    """إنشاء الجداول الأساسية إذا لم تكن موجودة"""
    
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

    conn = None
    try:
        conn = get_db()
        with conn.cursor() as cur:
            # تنفيذ كل أمر إنشاء
            for command in commands:
                cur.execute(command)
            
            conn.commit()
            logging.info("✅ تم تهيئة قاعدة البيانات بنجاح (الجداول جاهزة).")
            
    except Exception as e:
        logging.error(f"❌ خطأ أثناء تهيئة قاعدة البيانات: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # تشغيل التهيئة عند استدعاء الملف مباشرة
    initialize_database()
