import psycopg2
from psycopg2.extras import RealDictCursor
import config
import logging
import secrets
import traceback
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

# --- 2. إدارة المستخدمين والإحصائيات ---

def get_admin_dashboard_stats():
    """جلب إحصائيات لوحة التحكم للأدمن"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM users) as total,
                        (SELECT COUNT(*) FROM users WHERE is_activated = TRUE) as active,
                        (SELECT COUNT(*) FROM activation_codes WHERE is_used = FALSE) as codes
                """)
                result = cur.fetchone()
                return result if result else {'total': 0, 'active': 0, 'codes': 0}
    except Exception as e:
        logging.error(f"Error fetching stats: {e}")
        return {'total': 0, 'active': 0, 'codes': 0}

def get_all_users():
    """جلب قائمة آخر 20 مستخدم مسجل لإدارتهم"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated, expiry_date FROM users ORDER BY created_at DESC LIMIT 20")
                return cur.fetchall()
    except Exception as e:
        logging.error(f"Error fetching users: {e}")
        return []

def register_user_if_not_exists(user_id):
    """تسجيل مستخدم جديد تلقائياً"""
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
    """جلب بيانات حساب المستخدم بالكامل بنظام القاموس"""
    try:
        target_id = str(user_id).strip()
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (target_id,))
                return cur.fetchone()
    except Exception as e:
        logging.error(f"❌ خطأ في جلب بيانات المستخدم {user_id}: {e}")
        return None

def update_user_status(user_id, status):
    """تحديث حالة المستخدم (تفعيل أو إيقاف) من لوحة الإدارة"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_activated = %s WHERE user_id = %s",
                    (status, str(user_id))
                )
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error updating user status: {e}")
        return False

def add_new_user(user_id):
    """إضافة مستخدم جديد يدوياً"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, is_activated, created_at)
                    VALUES (%s, FALSE, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (str(user_id),))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"❌ Database Error in add_new_user: {e}")
        return False

# --- 3. إدارة التوكن والقنوات ---

def update_user_secret_token(user_id, new_token):
    """تحديث التوكن السري للمستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(user_id)))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error updating token: {e}")
        return False

def add_user_entity(user_id, entity_id, entity_name):
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
    """جلب القنوات المرتبطة بنظام القاموس (هام لفحص القيد الصارم)"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT user_id, entity_id, entity_name FROM entities WHERE user_id = %s", 
                    (str(user_id),)
                )
                return cur.fetchall()
    except Exception as e:
        logging.error(f"Error fetching user entities: {e}")
        return []

def delete_user_entity(user_id, entity_id):
    """حذف قناة مرتبطة نهائياً"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM entities WHERE user_id = %s AND entity_id = %s", 
                    (str(user_id), str(entity_id))
                )
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error in delete_user_entity: {e}")
        return False

# --- 4. نظام التفعيل وتوليد الأكواد ---

def add_subscription_code(code, days=30):
    """إضافة كود اشتراك جديد"""
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
    """تفعيل اشتراك المستخدم باستخدام كود"""
    try:
        if not code: return False, "⚠️ كود غير صالح"
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM activation_codes WHERE UPPER(code) = UPPER(%s)", (code.strip(),))
                code_data = cur.fetchone()
                
                if not code_data: return False, "❌ الكود غير موجود."
                if code_data['is_used']: return False, "⚠️ الكود مستخدم مسبقاً."
                
                days = code_data['days']
                expiry_date = datetime.now() + timedelta(days=days)
                
                cur.execute("UPDATE users SET is_activated = TRUE, expiry_date = %s WHERE user_id = %s", (expiry_date, str(user_id)))
                cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(user_id), code_data['code']))
                conn.commit()
                return True, f"✅ تم التفعيل لـ {days} يوم."
    except Exception as e:
        logging.error(f"‼️ خطأ في التفعيل: {traceback.format_exc()}")
        return False, "❌ فشل النظام."

def check_subscription(user_id):
    """التحقق من الاشتراك (متوافق مع الويب هوك)"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT is_activated, expiry_date FROM users WHERE user_id = %s", (str(user_id),))
                result = cur.fetchone()
                if result:
                    active = result['is_activated']
                    expiry = result['expiry_date']
                    if not active or (expiry and expiry < datetime.now().date()):
                        return False, expiry
                    return True, expiry
                return False, None
    except Exception as e:
        logging.error(f"Subscription Check Error: {e}")
        return False, None

def get_user_by_token(token):
    """جلب بيانات المستخدم الكاملة عبر التوكن"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE secret_token = %s", (token,))
                result = cur.fetchone()
                return dict(result) if result else None
    except Exception as e:
        logging.error(f"❌ Error in get_user_by_token: {e}")
        return None

def get_all_user_ids():
    """جلب قائمة بكل معرفات التلجرام للمستخدمين"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users")
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logging.error(f"❌ خطأ في جلب معرفات المستخدمين: {e}")
        return []
        


def delete_user(user_id):
    """حذف المستخدم من جميع الجداول المحتملة لضمان النتيجة"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # تحويل المعرف لنص صريح ونظيف
        target_id = str(user_id).strip()
        
        # 1. محاولة الحذف من جدول users
        cursor.execute("DELETE FROM users WHERE user_id = %s", (target_id,))
        rows_users = cursor.rowcount
        
        # 2. محاولة الحذف من جدول activation_codes (احتياطاً)
        cursor.execute("DELETE FROM activation_codes WHERE user_id = %s", (target_id,))
        rows_codes = cursor.rowcount
        
        conn.commit() # تثبيت الحذف في الجدولين
        
        cursor.close()
        conn.close()
        
        # إذا تم الحذف من أي جدول، نعتبرها نجحت
        total_deleted = rows_users + rows_codes
        print(f"📡 DEBUG: الحذف النهائي لـ {target_id} | الإجمالي: {total_deleted}")
        
        return total_deleted > 0
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ خطأ قاعدة البيانات: {e}")
        return False





        
def admin_activate_user(user_id, days=30):
    try:
        # هنا يتم استخدام عدد الأيام المختار (10, 30, 60, أو 90)
        expiry_date = datetime.now() + timedelta(days=int(days))
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_activated = TRUE, expiry_date = %s WHERE user_id = %s",
                    (expiry_date, str(user_id))
                )
                conn.commit()
                return True, expiry_date.strftime('%Y-%m-%d')
    except Exception as e:
        logging.error(f"Error in admin_activate_user: {e}")
        return False, None
