# security.py
import time
import datetime
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import re
from database import get_db

# --- الإعدادات الأمنية ---

# القائمة السوداء للكلمات المحظورة (حقن SQL وروابط مشبوهة)
FORBIDDEN_KEYWORDS = [
    'select ', 'drop ', 'delete ', 'insert ', 'update ', 'union ', 'table', 
    'http://', 'https://', 'www.', 't.me/', '.com', '.net', '.org'
]

# قاموس مؤقت لتخزين سرعة الطلبات (يبقى في الرام)
user_requests = {}

# --- الدوال الأساسية ---

def rate_limit(seconds=1):
    """منع المستخدم من إرسال طلبات متكررة بسرعة (Ant-Spam)"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user: return await func(update, context, *args, **kwargs)
            uid = update.effective_user.id
            current_time = time.time()
            if uid in user_requests and (current_time - user_requests[uid]) < seconds:
                if update.callback_query:
                    await update.callback_query.answer("⚠️ يرجى الانتظار قليلاً.. لا تضغط بسرعة!", show_alert=False)
                return 
            user_requests[uid] = current_time
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def check_malicious_content(text):
    """يفحص النص بحثاً عن محاولات حقن أو روابط محظورة"""
    if not text: return False
    lowered_text = text.lower()
    return any(word in lowered_text for word in FORBIDDEN_KEYWORDS)

def force_block_user(uid):
    """حظر نهائي ومباشر في الداتابيز عند اكتشاف محاولة تخريب"""
    with get_db() as conn:
        with conn.cursor() as cur:
            # حظر لمدة 100 سنة (بمثابة حظر نهائي)
            blocked_date = datetime.datetime.now() + datetime.timedelta(days=36500)
            cur.execute("""
                UPDATE users 
                SET block_level = 99, 
                    blocked_until = %s 
                WHERE user_id = %s
            """, (blocked_date, str(uid)))
            conn.commit()

def log_failed_attempt(uid):
    """تسجيل المحاولة الفاشلة وتطبيق الحظر التصاعدي (ساعة -> 24س -> 15يوم -> دائم)"""
    with get_db() as conn:
        with conn.cursor() as cur:
            # جلب العداد ومستوى الحظر الحالي من القاعدة
            cur.execute("SELECT failed_count, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res: return False, None, 0
            
            f_count = res[0] + 1
            b_level = res[1]
            
            if f_count >= 3:
                # رفع مستوى الحظر وتحديد المدة بناءً على المستوى الجديد
                new_level = b_level + 1
                
                if new_level == 1:
                    until = datetime.datetime.now() + datetime.timedelta(hours=1)
                    msg = "تم إيقافك لمدة ساعة بسبب محاولات خاطئة"
                elif new_level == 2:
                    until = datetime.datetime.now() + datetime.timedelta(hours=24)
                    msg = "تم إيقافك لمدة 24 ساعة (تكرار مخالفة)"
                elif new_level == 3:
                    until = datetime.datetime.now() + datetime.timedelta(days=15)
                    msg = "تم إيقافك لمدة 15 يوم (مخالفة جسيمة)"
                else:
                    until = datetime.datetime.now() + datetime.timedelta(days=36500)
                    msg = "تم حظرك بشكل دائم 🔒"
                
                cur.execute("""
                    UPDATE users 
                    SET failed_count = 0, 
                        blocked_until = %s, 
                        block_level = %s 
                    WHERE user_id = %s
                """, (until, new_level, str(uid)))
                conn.commit()
                return True, msg, 0
            else:
                # تحديث عداد المحاولات الفاشلة فقط
                cur.execute("UPDATE users SET failed_count = %s WHERE user_id = %s", (f_count, str(uid)))
                conn.commit()
                return False, None, f_count

def is_user_blocked(uid):
    """التحقق من الداتابيز إذا كان المستخدم محظوراً حالياً"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT blocked_until, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res or not res[0]: return False, 0
            
            blocked_until = res[0]
            if datetime.datetime.now() < blocked_until:
                # حساب الدقائق المتبقية للحظر
                remaining = int((blocked_until - datetime.datetime.now()).total_seconds() / 60)
                return True, max(remaining, 1)
            else:
                # انتهى وقت الحظر، نصفر عداد المحاولات (لكن نترك مستوى الحظر للمرة القادمة)
                cur.execute("UPDATE users SET failed_count = 0, blocked_until = NULL WHERE user_id = %s", (str(uid),))
                conn.commit()
    return False, 0

def sanitize_input(text):
    """تنظيف النصوص من وسوم HTML"""
    if not text: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()
