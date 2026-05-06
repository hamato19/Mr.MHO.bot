# services.py
import datetime
import config
from database import get_db
from psycopg2.extras import RealDictCursor

def get_time_remaining(expiry_date):
    """حساب الوقت المتبقي للاشتراك بتنسيق نصي جذاب"""
    if not expiry_date: 
        return "غير مفعل 🔓"
    
    now = datetime.datetime.now()
    if now > expiry_date: 
        return "منتهٍ 🛑"
    
    diff = expiry_date - now
    days = diff.days
    hours = diff.seconds // 3600
    
    if days > 0:
        return f"{days} يوم و {hours} ساعة"
    else:
        return f"{hours} ساعة فقط"

def get_user_data(uid):
    """جلب بيانات المستخدم كاملة من قاعدة البيانات"""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT secret_token, expiry_date, is_activated 
                FROM users WHERE user_id = %s
            """, (str(uid),))
            return cur.fetchone()

def get_user_entities(uid):
    """جلب القنوات المرتبطة بمستخدم معين"""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entity_id FROM entities WHERE user_id = %s", (str(uid),))
            return cur.fetchall()

def format_webhook_links(token, entities):
    """تجهيز روابط الويب هوك بشكل نصي منسق"""
    if not entities:
        return "⚠️ لا توجد قنوات مرتبطة حالياً."
    
    txt = "🌐 <b>روابط الويب هوك الخاصة بك:</b>\n\n"
    for ent in entities:
        target_id = ent['entity_id']
        txt += f"• القناة <code>{target_id}</code>:\n"
        txt += f"<code>{config.DOMAIN}/webhook/{token}/{target_id}</code>\n\n"
    return txt
