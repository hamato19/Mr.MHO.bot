import os
import datetime
import secrets
import requests
import asyncio
from database import get_db
from psycopg2.extras import RealDictCursor
import config

# --- منع النوم ---
async def keep_alive():
    """منع السيرفر من الدخول في وضع النوم في Render"""
    domain = os.getenv("DOMAIN") or config.DOMAIN
    while True:
        try: 
            if domain:
                requests.get(domain, timeout=10)
        except Exception: 
            pass
        await asyncio.sleep(600)

# --- إدارة المستخدمين ---
def initialize_user(uid):
    """إضافة المستخدم مع رمز سري افتراضي (الدالة المفقودة)"""
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
    """جلب كافة بيانات المستخدم"""
    with get_db() as conn:
        if conn is None: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            return cur.fetchone()

def update_user_token(uid, new_token):
    """تحديث رمز الويب هوك الخاص بالمستخدم"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
            conn.commit()

def get_user_language(uid):
    """جلب لغة المستخدم"""
    with get_db() as conn:
        if conn is None: return 'ar'
        with conn.cursor() as cur:
            cur.execute("SELECT language FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            return res[0] if res else 'ar'

# --- إدارة القنوات والويب هوك ---
def get_user_entities(uid):
    """جلب القنوات المرتبطة"""
    with get_db() as conn:
        if conn is None: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id, entity_name FROM entities WHERE user_id = %s", (str(uid),))
            return cur.fetchall()

def format_my_entities(uid):
    """تنسيق قائمة القنوات لزر 'قنواتي'"""
    entities = get_user_entities(uid)
    if not entities:
        return "⚠️ ليس لديك قنوات مرتبطة حالياً."
    txt = "📋 <b>قنواتك المرتبطة:</b>\n\n"
    for e in entities:
        txt += f"🔹 {e['entity_name']}\n<code>{e['entity_id']}</code>\n\n"
    return txt

def format_webhook_links(uid):
    """تنسيق روابط الويب هوك"""
    user = get_user_data(uid)
    entities = get_user_entities(uid)
    if not user: return "⚠️ خطأ في جلب البيانات."
    token = user.get('secret_token')
    domain = (os.getenv("DOMAIN") or config.DOMAIN).strip('/')
    if not entities: return "⚠️ لا توجد قنوات مرتبطة."
    txt = "🌐 <b>روابط الويب هوك:</b>\n\n"
    for e in entities:
        url = f"{domain}/webhook/{token}/{e['entity_id']}"
        txt += f"📍 {e['entity_name']}:\n<code>{url}</code>\n\n"
    return txt

# --- لوحة التحكم والاشتراكات ---
def get_admin_stats():
    """إحصائيات المالك (الدالة التي سببت الخطأ)"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                u_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM activation_codes WHERE is_used = FALSE")
                c_count = cur.fetchone()[0]
                return u_count, c_count
    except:
        return 0, 0

def redeem_code(uid, code_str):
    """تفعيل الاشتراك"""
    with get_db() as conn:
        if conn is None: return False, "❌ خطأ قاعدة بيانات"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM activation_codes WHERE code = %s AND is_used = FALSE", (code_str,))
            code = cur.fetchone()
            if not code: return False, "❌ الكود غير صحيح."
            days = code['days']
            now = datetime.datetime.now()
            new_expiry = now + datetime.timedelta(days=days)
            cur.execute("UPDATE users SET is_activated = TRUE, expiry_date = %s WHERE user_id = %s", (new_expiry, str(uid)))
            cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(uid), code_str))
            conn.commit()
            return True, f"✅ تم التفعيل حتى: {new_expiry.strftime('%Y-%m-%d')}"

def is_user_active(user):
    if not user or not user['is_activated']: return False
    if user['expiry_date'] and datetime.datetime.now() > user['expiry_date']: return False
    return True

def get_time_remaining(expiry_date):
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"
