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
        # يستخدم DATABASE_URL من متغيرات البيئة في Render
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
    """جلب قائمة آخر 20 مستخدم مسجل لإدارتهم"""
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT user_id, is_activated, expiry_date FROM users ORDER BY user_id DESC LIMIT 20")
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
    """جلب بيانات حساب المستخدم من عمود user_id (bigint)"""
    try:
        # تنظيف وتحويل الـ ID لضمان مطابقته لنوع bigint في Neon
        target_id = str(user_id).strip()
        
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (target_id,))
                return cur.fetchone()
    except Exception as e:
        logging.error(f"❌ خطأ في جلب بيانات المستخدم {user_id}: {e}")
        return None

# --- 3. إدارة التوكن والقنوات ---
def update_user_secret_token(user_id, new_token):
    """تحديث التوكن السري للمستخدم"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # تأكد من اسم الجدول؛ في الصورة السابقة كان اسمه activation_codes
                # إذا كان اسم الجدول users كما في الكود الحالي فاستخدمه
                cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(user_id)))
                conn.commit()
                return True # نكتفي بإرجاع True للتأكيد
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


def delete_user_entity(user_id, entity_id): # تم تغيير الاسم ليطابق main.py
    """حذف قناة مرتبطة نهائياً من قاعدة البيانات"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # التأكد من حذف السجل الخاص بالمستخدم والقناة المحددة
                cur.execute(
                    "DELETE FROM entities WHERE user_id = %s AND entity_id = %s", 
                    (str(user_id), str(entity_id))
                )
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error in delete_user_entity: {e}")
        return False

def delete_entity(user_id, entity_id):
    """حذف قناة مرتبطة"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM entities WHERE user_id = %s AND entity_id = %s", (str(user_id), str(entity_id)))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Error deleting entity: {e}")
        return False

# --- 4. نظام التفعيل وتوليد الأكواد ---

def add_subscription_code(code, days=30):
    """إضافة الكود الجاهز إلى قاعدة البيانات"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO activation_codes (code, days, is_used) VALUES (%s, %s, FALSE)",
                    (code, days)
                )
                conn.commit()
                logging.info(f"✅ تم حفظ الكود بنجاح: {code}")
                return True
    except Exception as e:
        logging.error(f"❌ Error in add_subscription_code: {e}")
        return False


def activate_user_with_code(user_id, code):
    """تفعيل اشتراك المستخدم"""
    try:
        if not code or not str(code).strip():
            return False, "⚠️ يرجى إدخال كود صالح."

        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM activation_codes WHERE UPPER(code) = UPPER(%s)", 
                    (code.strip(),)
                )
                code_data = cur.fetchone()
                
                if not code_data:
                    return False, "❌ الكود غير موجود في النظام."
                if code_data['is_used']:
                    return False, f"⚠️ هذا الكود مستخدم مسبقاً."
                
                days = code_data['days']
                expiry_date = datetime.now() + timedelta(days=days)
                
                cur.execute("""
                    UPDATE users 
                    SET is_activated = TRUE, expiry_date = %s 
                    WHERE user_id = %s
                """, (expiry_date, str(user_id)))
                
                cur.execute("""
                    UPDATE activation_codes 
                    SET is_used = TRUE, used_by = %s 
                    WHERE code = %s
                """, (str(user_id), code_data['code']))
                
                conn.commit()
                return True, f"✅ تم التفعيل لمدة {days} يوم.\nينتهي في: {expiry_date.strftime('%Y-%m-%d')}"

    except Exception as e:
        logging.error(f"‼️ خطأ في التفعيل: {traceback.format_exc()}")
        return False, f"❌ فشل النظام: {str(e)}"

def update_user_status(user_id, status):
    """تحديث حالة المستخدم (تفعيل أو إيقاف)"""
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
    """إضافة مستخدم جديد لقاعدة البيانات إذا لم يكن موجوداً (تستخدم مع زر الموافقة)"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                query = """
                INSERT INTO users (user_id, is_activated, created_at)
                VALUES (%s, FALSE, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO NOTHING;
                """
                cur.execute(query, (str(user_id),))
                conn.commit()
                logging.info(f"👤 تم تسجيل مستخدم جديد بنجاح: {user_id}")
                return True
    except Exception as e:
        logging.error(f"❌ Database Error in add_new_user: {e}")
        return False
def get_user_entities(user_id):
    """جلب جميع القنوات المرتبطة بمستخدم محدد"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # نجلب المعرف (ID) والاسم (Name) من جدول entities
                cur.execute(
                    "SELECT user_id, entity_id, entity_name FROM entities WHERE user_id = %s", 
                    (str(user_id),)
                )
                return cur.fetchall() # يعيد قائمة بالصفوف
    except Exception as e:
        logging.error(f"Error fetching user entities: {e}")
        return []

def check_subscription(user_id):
    """التحقق من حالة الاشتراك وتاريخ الانتهاء"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT is_active, expiry_date 
                    FROM users 
                    WHERE user_id = %s
                """, (str(user_id),))
                result = cur.fetchone()
                
                if result:
                    is_active, expiry_date = result
                    # إذا كان الحساب معطل يدوياً أو التاريخ انتهى
                    if not is_active or expiry_date < datetime.date.today():
                        return False, expiry_date
                    return True, expiry_date
                return False, None
    except Exception as e:
        logging.error(f"Subscription Check Error: {e}")
        return False, None

def update_subscription(user_id, months=1):
    """تجديد الاشتراك للمشترك"""
    days = months * 30
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET is_active = TRUE, 
                        expiry_date = GREATEST(expiry_date, CURRENT_DATE) + INTERVAL '%s days'
                    WHERE user_id = %s
                """, (days, str(user_id)))
                conn.commit()
                return True
    except Exception as e:
        logging.error(f"Update Subscription Error: {e}")
        return False

def get_user_by_token(token):
    """جلب بيانات المستخدم الكاملة للتحقق من الاشتراك"""
    try:
        with get_db() as conn:
            # استخدام RealDictCursor لضمان التعامل مع النتائج كقاموس بايثون
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # أضفنا is_activated و expiry_date للأمر
                cur.execute("""
                    SELECT user_id, secret_token, is_activated, expiry_date 
                    FROM users 
                    WHERE secret_token = %s
                """, (token,))
                
                result = cur.fetchone()
                
                # تحويل النتيجة لقاموس بسيط لضمان التوافق مع الكود في الويب هوك
                return dict(result) if result else None
    except Exception as e:
        logging.error(f"❌ Error in get_user_by_token: {e}")
        return None
