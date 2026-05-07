# services.py
import datetime
import secrets
import requests
import time
from database import get_db
from psycopg2.extras import RealDictCursor
import config

def keep_alive():
    """منع السيرفر من الدخول في وضع النوم"""
    while True:
        try: 
            if config.DOMAIN:
                requests.get(config.DOMAIN, timeout=10)
        except Exception: 
            pass
        time.sleep(20)

def initialize_user(uid):
    """إضافة المستخدم لقاعدة البيانات"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, secret_token) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id) DO NOTHING
            """, (str(uid), secrets.token_hex(8)))
            conn.commit()

def get_user_data(uid):
    """جلب بيانات المستخدم"""
    with get_db() as conn:
        if conn is None: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            return cur.fetchone()

def update_user_token(uid, new_token):
    """تحديث رمز الويب هوك"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
            conn.commit()

def add_entity(uid, tid, name="قناة/مجموعة"):
    """ربط القناة بالمستخدم مع دعم حفظ الاسم"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO entities (user_id, entity_id, entity_name) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (user_id, entity_id) 
                DO UPDATE SET entity_name = EXCLUDED.entity_name
            """, (str(uid), str(tid), name))
            conn.commit()

def get_user_entities(uid):
    """جلب القنوات المرتبطة"""
    with get_db() as conn:
        if conn is None: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id, entity_name FROM entities WHERE user_id = %s", (str(uid),))
            return cur.fetchall()

def delete_entity(user_id, entity_id):
    """حذف قناة مرتبطة"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM entities WHERE user_id = %s AND entity_id = %s",
                (str(user_id), str(entity_id))
            )
            conn.commit()

# --- دالة تفعيل الاشتراك عبر الكود ---
def redeem_code(uid, code_str):
    """تفعيل اشتراك المستخدم باستخدام كود"""
    with get_db() as conn:
        if conn is None: return False, "❌ فشل الاتصال بقاعدة البيانات"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # التأكد من صحة الكود في جدول activation_codes (المعرف في init_db)
            cur.execute("SELECT * FROM activation_codes WHERE code = %s AND is_used = FALSE", (code_str,))
            code = cur.fetchone()
            
            if not code:
                return False, "❌ الكود غير صحيح، منتهي، أو تم استخدامه مسبقاً."
            
            days = code['days']
            
            # جلب بيانات المستخدم الحالية لمعرفة تاريخ الانتهاء القديم
            cur.execute("SELECT expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            # إذا كان لديه اشتراك فعال، نضيف الأيام الجديدة فوق القديمة
            now = datetime.datetime.now()
            if user and user['expiry_date'] and user['expiry_date'] > now:
                new_expiry = user['expiry_date'] + datetime.timedelta(days=days)
            else:
                new_expiry = now + datetime.timedelta(days=days)
            
            # تحديث حالة المستخدم واستهلاك الكود
            cur.execute("""
                UPDATE users 
                SET is_activated = TRUE, expiry_date = %s 
                WHERE user_id = %s
            """, (new_expiry, str(uid)))
            
            cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(uid), code_str))
            
            conn.commit()
            return True, f"✅ تم تفعيل الاشتراك بنجاح!\n⏳ ينتهي في: {new_expiry.strftime('%Y-%m-%d')}"

def is_user_active(user):
    """فحص هل المستخدم مفعل واشتراكه ساري"""
    if not user or not user['is_activated']: return False
    if user['expiry_date'] and datetime.datetime.now() > user['expiry_date']: return False
    return True

def get_time_remaining(expiry_date):
    """حساب الوقت المتبقي"""
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"

def format_webhook_links(token, entities):
    """تنسيق الروابط لإرسالها للمستخدم"""
    if not entities: return "⚠️ لا توجد قنوات مرتبطة."
    txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
    for e in entities:
        eid = e['entity_id']
        ename = e.get('entity_name', 'قناة غير مسمية')
        txt += f"📍 {ename}:\n<code>{config.DOMAIN}/webhook/{token}/{eid}</code>\n\n"
    return txt
