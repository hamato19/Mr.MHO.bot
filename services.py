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
    """منع السيرفر من الدخول في وضع النوم في Render"""
    domain = os.getenv("DOMAIN") or config.DOMAIN
    while True:
        try: 
            if domain:
                requests.get(domain, timeout=10)
        except Exception: 
            pass
        await asyncio.sleep(600)

def get_user_data(uid):
    """جلب كافة بيانات المستخدم"""
    with get_db() as conn:
        if conn is None: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            return cur.fetchone()

def update_user_token(uid, new_token):
    """تحديث رمز الويب هوك السري"""
    with get_db() as conn:
        if conn is None: return
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
            conn.commit()

def get_user_entities(uid):
    """جلب القنوات/المجموعات المرتبطة"""
    with get_db() as conn:
        if conn is None: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id, entity_name FROM entities WHERE user_id = %s", (str(uid),))
            return cur.fetchall()

def format_webhook_links(uid):
    """توليد وتنسيق روابط الويب هوك للمستخدم"""
    user = get_user_data(uid)
    entities = get_user_entities(uid)
    
    if not user: return "⚠️ خطأ في جلب بيانات المستخدم."
    
    token = user.get('secret_token')
    # جلب الدومين وتصحيحه
    domain = (os.getenv("DOMAIN") or config.DOMAIN).strip('/')

    if not domain:
        return "⚠️ خطأ: متغير DOMAIN غير معرف في الإعدادات."
    
    if not entities:
        return "⚠️ لا توجد قنوات مرتبطة. أضف البوت للقناة أولاً."

    txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
    for e in entities:
        eid = e['entity_id']
        ename = e.get('entity_name') or 'قناة غير مسمية'
        url = f"{domain}/webhook/{token}/{eid}"
        txt += f"📍 {ename}:\n<code>{url}</code>\n\n"
    
    return txt + "✅ <i>انسخ الرابط المناسب وضعه في TradingView.</i>"

# الدوال الإضافية (اللغة والاشتراك)
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
