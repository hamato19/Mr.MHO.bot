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

# --- 1. دوال إدارة المستخدمين (Admin & General) ---

def get_admin_dashboard_stats():
    """جلب إحصائيات لوحة التحكم للأدمن"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # إجمالي المستخدمين
                cur.execute("SELECT COUNT(*) FROM users")
                total_users = cur.fetchone()[0]
                
                # المستخدمين المفعلين
                cur.execute("SELECT COUNT(*) FROM users WHERE is_activated = TRUE")
                active_users = cur.fetchone()[0]
                
                # الأكواد المتاحة
                cur.execute("SELECT COUNT(*) FROM activation_codes WHERE is_used = FALSE")
                available_codes = cur.fetchone()[0]
                
                return total_users, active_users, available_codes
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        return 0, 0, 0

def register_user_if_not_exists(user_id):
    """تسجيل مستخدم جديد إذا لم يكن موجوداً مع توليد توكن سري تلقائي"""
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
    """جلب بيانات حساب المستخدم (لزر حسابي)"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (str(user_id),))
                return cur.fetchone()
    except Exception as e:
        logging.error(f"Error fetching profile: {e}")
        return None

# --- 2. دوال الرموز والويب هوك (Webhook & Tokens) ---

def update_user_secret_token(user_id):
    """توليد رمز جديد (لزر توليد رمز جديد)"""
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

# --- 3. دوال إدارة الكيانات (Entities/Channels) ---

def add_entity(user_id, entity_id, entity_name):
    """ربط قناة أو مجموعة جديدة"""
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
    """جلب كافة الكيانات المربوطة بمستخدم معين"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM entities WHERE user_id = %s", (str(user_id),))
                return cur.fetchall()
    except Exception as e:
        logging.error(f"Error fetching entities: {e}")
        return []

# --- 4. نظام التفعيل (Activation System) ---

def create_activation_code(code, days):
    """إنشاء كود تفعيل جديد (خاص بالأدمن)"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO activation_codes (code, days) VALUES (%s, %s)", (code, days))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error creating code: {e}")
        return False

def activate_user_with_code(user_id, code):
    """تفعيل اشتراك المستخدم باستخدام كود"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # التأكد من صحة الكود
                cur.execute("SELECT * FROM activation_codes WHERE code = %s AND is_used = FALSE", (code,))
                code_data = cur.fetchone()
                
                if not code_data:
                    return False, "الكود غير صالح أو مستخدم مسبقاً."
                
                days = code_data['days']
                expiry_date = datetime.now() + timedelta(days=days)
                
                # تحديث المستخدم وتحديد الكود كمستخدم
                cur.execute("""
                    UPDATE users 
                    SET is_activated = TRUE, expiry_date = %s 
                    WHERE user_id = %s
                """, (expiry_date, str(user_id)))
                
                cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(user_id), code))
                
                conn.commit()
                return True, f"تم التفعيل بنجاح لمدة {days} يوم."
    except Exception as e:
        logging.error(f"Error in activation: {e}")
        return False, "حدث خطأ فني أثناء التفعيل."

