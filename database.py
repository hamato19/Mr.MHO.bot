import psycopg2
from psycopg2.extras import RealDictCursor
import config
import logging
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@contextmanager
def get_db():
    """إنشاء اتصال بقاعدة البيانات مع ضمان الإغلاق التلقائي"""
    conn = None
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
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

# --- 1. التهيئة ---
def init_db():
    """تهيئة الجداول عند بدء التشغيل"""
    try:
        from init_db import initialize_database
        initialize_database()
        logging.info("✅ تم استدعاء تهيئة قاعدة البيانات بنجاح.")
    except Exception as e:
        logging.error(f"❌ فشل في تهيئة الجداول: {e}")

# --- 2. إدارة المستخدمين والاحصائيات ---

def get_admin_dashboard_stats():
    """جلب إحصائيات لوحة التحكم للأدمن باستعلام واحد سريع"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM users) as total,
                        (SELECT COUNT(*) FROM users WHERE is_activated = TRUE) as active,
                        (SELECT COUNT(*) FROM activation_codes WHERE is_used = FALSE) as codes
                """)
                return cur.fetchone()
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        return 0, 0, 0

def get_all_users():
    """جلب قائمة المستخدمين للإدارة"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated, expiry_date FROM users ORDER BY id DESC LIMIT 20")
                return cur.fetchall()
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return []

def register_user_if_not_exists(user_id):
    """تسجيل مستخدم جديد"""
    secret_token = secrets.token_urlsafe(24)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, secret_token)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (str(user_id), secret_token))
                conn.commit()
    except Exception as e:
        logging.error(f"Error registering user: {e}")

def get_user_profile(user_id):
    """بيانات ملف المستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(user_id),))
                return cur.fetchone()
    except Exception as e:
        logging.error(f"Error fetching profile: {e}")
        return None

# --- 3. إدارة التوكن والقنوات ---

def update_user_secret_token(user_id):
    """تحديث رمز الويب هوك الخاص بالمستخدم"""
    new_token = secrets.token_urlsafe(24)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(user_id)))
                conn.commit()
                return new_token
    except Exception as e:
        logging.error(f"Error updating token: {e}")
        return None

def add_entity(user_id, entity_id, entity_name):
    """إضافة قناة أو مجموعة للمستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO entities (user_id, entity_id, entity_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, entity_id) DO UPDATE SET entity_name = EXCLUDED.entity_name
                """, (str(user_id), str(entity_id), entity_name))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error adding entity: {e}")
        return False

def get_user_entities(user_id):
    """جلب قنوات المستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT entity_id, entity_name FROM entities WHERE user_id = %s", (str(user_id),))
                return cur.fetchall()
    except Exception as e:
        logging.error(f"Error fetching entities: {e}")
        return []

# --- 4. نظام التفعيل وتوليد الأكواد (إصلاح خطأ column days) ---

def add_subscription_code(code, days=30):
    """إضافة كود جديد لقاعدة البيانات"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO activation_codes (code, days, is_used) VALUES (%s, %s, FALSE)",
                    (code, days)
                )
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"❌ Error in add_subscription_code: {e}")
        return False

def activate_user_with_code(user_id, code):
    """استخدام الكود لتفعيل اشتراك المستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM activation_codes WHERE code = %s AND is_used = FALSE", (code,))
                code_data = cur.fetchone()
                
                if not code_data:
                    return False, "⚠️ الكود غير صالح أو مستخدم مسبقاً."
                
                days = code_data['days']
                expiry_date = datetime.now() + timedelta(days=days)
                
                cur.execute("""
                    UPDATE users 
                    SET is_activated = TRUE, expiry_date = %s 
                    WHERE user_id = %s
                """, (expiry_date, str(user_id)))
                
                cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(user_id), code))
                
                conn.commit()
                return True, f"✅ تم التفعيل بنجاح لمدة {days} يوم."
    except Exception as e:
        logging.error(f"Error in activation: {e}")
        return False, "❌ حدث خطأ فني أثناء التفعيل."

# --- 5. نظام التفعيل وتوليد الأكواد المطور ---

def add_subscription_code(days=30):
    """
    توليد كود اشتراك فريد يبدأ بـ Smo- وحفظه في القاعدة
    """
    # توليد رمز عشوائي ودمجه مع البادئة المطلوبة
    random_suffix = secrets.token_hex(4).upper() # توليد 8 رموز عشوائية
    new_code = f"Smo-{random_suffix}"
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO activation_codes (code, days, is_used) VALUES (%s, %s, FALSE)",
                    (new_code, days)
                )
                conn.commit()
                logging.info(f"✅ تم توليد كود جديد: {new_code}")
                return new_code # نرجع الكود لكي يتم عرضه للأدمن في تلجرام
    except Exception as e:
        logging.error(f"❌ Error in add_subscription_code: {e}")
        return None

