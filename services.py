import os, datetime, secrets, requests, asyncio
from database import get_db
from psycopg2.extras import RealDictCursor
import config

def get_user_data(uid):
    """جلب بيانات المستخدم كاملة (بما فيها الرمز السري واللغة)"""
    with get_db() as conn:
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (str(uid),))
            return cur.fetchone()

def update_user_token(uid, new_token):
    """تحديث الرمز السري فوراً في قاعدة البيانات"""
    with get_db() as conn:
        if not conn: return
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET secret_token = %s WHERE user_id = %s", (new_token, str(uid)))
            conn.commit()

def format_webhook_links(uid):
    """توليد الروابط بناءً على بيانات المستخدم والقنوات المرتبطة"""
    user = get_user_data(uid)
    entities = get_user_entities(uid)
    token = user.get('secret_token') if user else None
    domain = os.getenv("DOMAIN") or config.DOMAIN
    domain = domain.strip('/') if domain else ""

    if not domain: return "⚠️ خطأ: متغير DOMAIN غير معرف في Render."
    if not token: return "⚠️ لا يوجد رمز سري، اضغط على 'توليد رمز جديد'."
    if not entities: return "⚠️ لا توجد قنوات مرتبطة. أضف قناة أولاً."

    txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
    for e in entities:
        url = f"{domain}/webhook/{token}/{e['entity_id']}"
        txt += f"📍 {e['entity_name']}:\n<code>{url}</code>\n\n"
    return txt + "✅ <i>انسخ الرابط وضعه في TradingView.</i>"

# ... دالة add_entity و get_user_entities تبقى كما هي في كودك الأخير ...
