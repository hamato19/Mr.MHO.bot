# services.py
import datetime
import secrets
import requests
import time
from database import get_db
from psycopg2.extras import RealDictCursor
import config

def keep_alive():
    """هذه هي الدالة المطلوبة لمنع السيرفر من النوم"""
    while True:
        try: 
            # يرسل طلب لنفسه كل 20 ثانية ليبقى السيرفر شغال
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

def add_entity(uid, tid):
    """ربط قناة جديدة"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("INSERT INTO entities (user_id, entity_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(uid), tid))
            conn.commit()

def get_user_entities(uid):
    """جلب القنوات المرتبطة"""
    with get_db() as conn:
        if conn is None: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
            return cur.fetchall()

def is_user_active(user):
    """فحص الاشتراك"""
    if not user or not user['is_activated']: return False
    if user['expiry_date'] and datetime.datetime.now() > user['expiry_date']: return False
    return True

def get_time_remaining(expiry_date):
    """تنسيق الوقت المتبقي"""
    if not expiry_date: return "غير مفعل 🔓"
    now = datetime.datetime.now()
    if now > expiry_date: return "منتهٍ 🛑"
    diff = expiry_date - now
    return f"{diff.days} يوم و {diff.seconds // 3600} ساعة"

def format_webhook_links(token, entities):
    """تجهيز الروابط"""
    if not entities: return "⚠️ لا توجد قنوات مرتبطة."
    txt = "🌐 <b>روابط الويب هوك:</b>\n\n"
    for e in entities:
        txt += f"• <code>{config.DOMAIN}/webhook/{token}/{e['entity_id']}</code>\n"
    return txt
