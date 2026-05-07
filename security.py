# security.py
import time
import datetime
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import re
from database import get_db

# --- الإعدادات الأمنية الصارمة ---

# القائمة السوداء الموسعة (تشمل محاولات تخريب قواعد البيانات والسكريبتات الخبيثة)
FORBIDDEN_PATTERNS = [
    r'select\s+.*from', r'drop\s+table', r'delete\s+from', r'truncate\s+',
    r'insert\s+into', r'update\s+.*set', r'union\s+select', r'script>',
    r'--' , r'\/\*', r'\*\/', r'xp_', r'exec\s+'
]

# الكلمات المحظورة (روابط ومنصات منافسة أو مشبوهة)
FORBIDDEN_WORDS = [
    'http://', 'https://', 'www.', 't.me/', '.com', '.net', '.org', 
    'botfather', 'token', 'api_key'
]

user_requests = {}

# --- الدوال الأساسية ---

def rate_limit(seconds=2):
    """منع السبام (Ant-Spam) بصرامة أعلى"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user: return await func(update, context, *args, **kwargs)
            uid = update.effective_user.id
            current_time = time.time()
            if uid in user_requests and (current_time - user_requests[uid]) < seconds:
                if update.callback_query:
                    await update.callback_query.answer("⚠️ هدوء! لا تضغط بسرعة.", show_alert=False)
                return 
            user_requests[uid] = current_time
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def check_malicious_content(text):
    """فحص النص بذكاء ضد الروابط والأنماط التخريبية"""
    if not text: return False
    lowered_text = text.lower()
    
    # فحص الروابط والكلمات
    if any(word in lowered_text for word in FORBIDDEN_WORDS): return True
    # فحص أنماط SQL Injection عبر Regex
    if any(re.search(pattern, lowered_text) for pattern in FORBIDDEN_PATTERNS): return True
    
    return False

def force_block_user(uid):
    """حظر نهائي ومباشر (Level 99)"""
    with get_db() as conn:
        with conn.cursor() as cur:
            blocked_date = datetime.datetime.now() + datetime.timedelta(days=36500)
            cur.execute("""
                UPDATE users SET block_level = 99, blocked_until = %s WHERE user_id = %s
            """, (blocked_date, str(uid)))
            conn.commit()

def is_user_blocked(uid):
    """التحقق من حالة الحظر مع تنظيف تلقائي إذا انتهت المدة"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT blocked_until, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res or not res[0]: return False, 0
            
            if datetime.datetime.now() < res[0]:
                remaining = int((res[0] - datetime.datetime.now()).total_seconds() / 60)
                return True, max(remaining, 1)
            else:
                cur.execute("UPDATE users SET failed_count = 0, blocked_until = NULL WHERE user_id = %s", (str(uid),))
                conn.commit()
    return False, 0

def log_failed_attempt(uid):
    """نظام الحظر التصاعدي الصارم"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT failed_count, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res: return False, "غير مسجل", 0
            
            f_count = res[0] + 1
            b_level = res[1]
            
            if f_count >= 3:
                new_level = b_level + 1
                durations = {1: (1, "ساعة واحدة"), 2: (24, "24 ساعة"), 3: (360, "15 يوم")}
                hours, label = durations.get(new_level, (876000, "حظر دائم 🔒"))
                
                until = datetime.datetime.now() + datetime.timedelta(hours=hours)
                cur.execute("""
                    UPDATE users SET failed_count = 0, blocked_until = %s, block_level = %s WHERE user_id = %s
                """, (until, new_level, str(uid)))
                conn.commit()
                return True, f"تم إيقافك لمدة {label}", 0
            else:
                cur.execute("UPDATE users SET failed_count = %s WHERE user_id = %s", (f_count, str(uid)))
                conn.commit()
                return False, None, f_count

def sanitize_input(text):
    """تنظيف النص من أي شوائب برمجية"""
    if not text: return ""
    text = re.sub(r'<.*?>', '', text) # حذف HTML
    text = re.sub(r'[;\'\"\\/]', '', text) # حذف رموز كسر الاستعلامات
    return text.strip()

# --- الدالة الكبرى لإدارة التفعيل والأمن ---

async def process_security_check(update, context, uid, raw_text):
    import config, database, keyboards
    
    # 1. فحص الحظر المسبق
    blocked, mins = is_user_blocked(uid)
    if blocked:
        await update.message.reply_text(f"🚫 <b>أنت مقيد مؤقتاً</b>\nيرجى الانتظار: <code>{mins}</code> دقيقة.", parse_mode='HTML')
        return

    # 2. فحص المحتوى الخبيث
    if check_malicious_content(raw_text):
        force_block_user(uid)
        alert = f"🚨 <b>محاولة اختراق!</b>\n👤ID: <code>{uid}</code>\n📝النص: <code>{raw_text}</code>\n⚖️الإجراء: حظر Level 99"
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=alert, parse_mode='HTML')
        await update.message.reply_text("⛔️ تم رصد نشاط مخالف. تم حظر حسابك نهائياً.")
        return

    # 3. محاولة التفعيل
    clean_code = sanitize_input(raw_text)
    success, msg = database.activate_user_with_code(uid, clean_code)

    if success:
        context.user_data['awaiting_code'] = False
        # تنبيه الأدمن بالنجاح
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"✅ <b>تفعيل ناجح</b>\n👤ID: <code>{uid}</code>\n🎫الكود: <code>{clean_code}</code>", parse_mode='HTML')
        await update.message.reply_text(f"✅ {msg}", reply_markup=await keyboards.get_main_menu(uid, (await context.bot.get_me()).username))
    else:
        # 4. فشل التفعيل والحظر التصاعدي
        is_blocked, b_msg, f_count = log_failed_attempt(uid)
        if is_blocked:
            alert = f"🚫 <b>حظر تلقائي</b>\n👤ID: <code>{uid}</code>\n⚠️السبب: تخمين كود\nℹ️النتيجة: {b_msg}"
            await context.bot.send_message(chat_id=config.ADMIN_ID, text=alert, parse_mode='HTML')
            await update.message.reply_text(f"🚫 <b>{b_msg}</b>", parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ كود غير صحيح. متبقي <b>{3-f_count}</b> محاولات.", parse_mode='HTML')
