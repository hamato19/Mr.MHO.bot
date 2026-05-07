# services.py
import os
import datetime
import secrets
import requests
import asyncio
from database import get_db
from psycopg2.extras import RealDictCursor
import config

async def keep_alive():
    """منع السيرفر من الدخول في وضع النوم"""
    domain = os.getenv("DOMAIN") or config.DOMAIN
    while True:
        try: 
            if domain:
                requests.get(domain, timeout=10)
        except Exception: 
            pass
        await asyncio.sleep(600)

def initialize_user(uid):
    """إضافة المستخدم مع رمز سري افتراضي"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, secret_token) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id) DO NOTHING
            """, (str(uid), secrets.token_hex(8)))
            conn.commit()

def set_user_language(uid, lang):
    """حفظ لغة المستخدم"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET language = %s WHERE user_id = %s", (lang, str(uid)))
            conn.commit()

def get_user_language(uid):
    """جلب لغة المستخدم"""
    with get_db() as conn:
        if conn is None: return 'ar'
        with conn.cursor() as cur:
            cur.execute("SELECT language FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            return res[0] if res else 'ar'

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

def add_entity(uid, tid, name="قناة/مجموعة"):
    """ربط القناة بالمستخدم مع حل مشكلة التعارض"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO entities (user_id, entity_id, entity_name) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (entity_id) 
                DO UPDATE SET 
                    user_id = EXCLUDED.user_id,
                    entity_name = EXCLUDED.entity_name
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

def redeem_code(uid, code_str):
    """تفعيل اشتراك المستخدم"""
    with get_db() as conn:
        if conn is None: return False, "❌ فشل الاتصال بقاعدة البيانات"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM activation_codes WHERE code = %s AND is_used = FALSE", (code_str,))
            code = cur.fetchone()
            
            if not code:
                return False, "❌ الكود غير صحيح أو مستخدم."
            
            days = code['days']
            cur.execute("SELECT expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            now = datetime.datetime.now()
            if user and user['expiry_date'] and user['expiry_date'] > now:
                new_expiry = user['expiry_date'] + datetime.timedelta(days=days)
            else:
                new_expiry = now + datetime.timedelta(days=days)
            
            cur.execute("""
                UPDATE users SET is_activated = TRUE, expiry_date = %s WHERE user_id = %s
            """, (new_expiry, str(uid)))
            cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s WHERE code = %s", (str(uid), code_str))
            conn.commit()
            return True, f"✅ تفعيل بنجاح!\n⏳ ينتهي: {new_expiry.strftime('%Y-%m-%d')}"

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

def format_webhook_links(token, entities):
    """تنسيق الروابط باستخدام الدومين من Render"""
    # الأولوية لمتغير البيئة في Render، ثم ملف الكوفنج
    domain = os.getenv("DOMAIN") or config.DOMAIN
    domain = domain.strip('/') if domain else ""

    if not domain:
        return "⚠️ خطأ: متغير DOMAIN غير معرف في Render."
    
    if not entities:
        return "⚠️ لا توجد قنوات مرتبطة."

    txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
    for e in entities:
        eid = e['entity_id']
        ename = e.get('entity_name') or 'قناة غير مسمية'
        url = f"{domain}/webhook/{token}/{eid}"
        txt += f"📍 {ename}:\n<code>{url}</code>\n\n"
    
    txt += "✅ <i>انسخ الرابط المناسب وضعه في TradingView.</i>"
    return txt
