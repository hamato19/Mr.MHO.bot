# security.py
import time
import datetime
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import re
from database import get_db

# --- الإعدادات الأمنية الصارمة (سمو الأرقام) ---

FORBIDDEN_PATTERNS = [
    r'select\s+.*from', r'drop\s+table', r'delete\s+from', r'truncate\s+',
    r'insert\s+into', r'update\s+.*set', r'union\s+select', r'script>',
    r'--' , r'\/\*', r'\*\/', r'xp_', r'exec\s+'
]

FORBIDDEN_WORDS = [
    'http://', 'https://', 'www.', 't.me/', '.com', '.net', '.org', 
    'botfather', 'token', 'api_key'
]

user_requests = {}

# --- الدوال الأمنية ---

def rate_limit(seconds=2):
    """منع السبام"""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user: return await func(update, context, *args, **kwargs)
            uid = update.effective_user.id
            current_time = time.time()
            if uid in user_requests and (current_time - user_requests[uid]) < seconds:
                return 
            user_requests[uid] = current_time
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

def check_malicious_content(text):
    """كشف الحقن والروابط"""
    if not text: return False
    lowered = text.lower()
    if any(word in lowered for word in FORBIDDEN_WORDS): return True
    if any(re.search(pattern, lowered) for pattern in FORBIDDEN_PATTERNS): return True
    return False

def force_block_user(uid):
    """حظر نهائي فوري (Level 99)"""
    with get_db() as conn:
        with conn.cursor() as cur:
            blocked_until = datetime.datetime.now() + datetime.timedelta(days=36500)
            cur.execute("""
                UPDATE users SET block_level = 99, blocked_until = %s WHERE user_id = %s
            """, (blocked_until, str(uid)))
            conn.commit()

def log_failed_attempt(uid):
    """نظام العقوبات التصاعدي الجديد"""
    import config
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT failed_count, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res: return False, "", 0
            
            f_count = res[0] + 1
            b_level = res[1]
            
            if f_count >= 3:
                new_level = b_level + 1
                
                if new_level == 1:
                    # المرة الأولى: إيقاف يوم
                    until = datetime.datetime.now() + datetime.timedelta(days=1)
                    msg = "🚫 تم إيقاف حسابك لمدة 24 ساعة بسبب إدخال أكواد خاطئة."
                elif new_level == 2:
                    # المرة الثانية: إيقاف 5 أيام
                    until = datetime.datetime.now() + datetime.timedelta(days=5)
                    msg = "🚫 تم إيقاف حسابك لمدة 5 أيام (تكرار محاولات خاطئة)."
                else:
                    # المرة الثالثة أو أكثر: حظر دائم وطلب تواصل مع الإدارة
                    until = datetime.datetime.now() + datetime.timedelta(days=36500)
                    msg = f"🔒 <b>تم حظر حسابك بشكل نهائي!</b>\n\nلفك الحظر يرجى التواصل مع الإدارة: {config.SUPPORT_LINK}"
                
                cur.execute("""
                    UPDATE users SET failed_count = 0, blocked_until = %s, block_level = %s 
                    WHERE user_id = %s
                """, (until, new_level, str(uid)))
                conn.commit()
                return True, msg, 0
            else:
                cur.execute("UPDATE users SET failed_count = %s WHERE user_id = %s", (f_count, str(uid)))
                conn.commit()
                return False, "", f_count

def is_user_blocked(uid):
    """فحص حالة الحظر من الداتابيز"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT blocked_until, block_level FROM users WHERE user_id = %s", (str(uid),))
            res = cur.fetchone()
            if not res or not res[0]: return False, 0, 0
            
            if datetime.datetime.now() < res[0]:
                remaining_hours = int((res[0] - datetime.datetime.now()).total_seconds() / 3600)
                return True, max(remaining_hours, 1), res[1]
            return False, 0, 0

def sanitize_input(text):
    """تنظيف المدخلات"""
    if not text: return ""
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'[;\'\"\\/]', '', text)
    return text.strip()

# --- الدالة الرئيسية للفحص وإرسال المعلومات للادمن ---

async def process_security_check(update, context, uid, raw_text):
    import config, database, keyboards
    
    # 1. التحقق من الحظر الحالي
    blocked, hours_left, level = is_user_blocked(uid)
    if blocked:
        if level >= 3:
            msg = f"🔒 حسابك محظور بشكل دائم.\nللمراجعة تواصل مع الإدارة: {config.SUPPORT_LINK}"
        else:
            msg = f"🚫 حسابك موقف حالياً. يرجى الانتظار <code>{hours_left}</code> ساعة."
        await update.message.reply_text(msg, parse_mode='HTML')
        return

    # 2. فحص المحتوى التخريبي (حظر فوري)
    if check_malicious_content(raw_text):
        force_block_user(uid)
        alert = (f"🚨 <b>تنبيه اختراق!</b>\n"
                 f"👤 المستخدم: <code>{uid}</code>\n"
                 f"📝 النص: <code>{raw_text}</code>\n"
                 f"⚖️ الإجراء: <b>حظر نهائي Level 99</b>")
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=alert, parse_mode='HTML')
        await update.message.reply_text("⛔️ تم رصد نشاط مشبوه.. تم حظر حسابك نهائياً.")
        return

    # 3. محاولة التفعيل
    clean_code = sanitize_input(raw_text)
    success, result_msg = database.activate_user_with_code(uid, clean_code)

    if success:
        context.user_data['awaiting_code'] = False
        admin_msg = f"✅ <b>تفعيل ناجح</b>\n👤 مستخدم: <code>{uid}</code>\n🎫 كود: <code>{clean_code}</code>"
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=admin_msg, parse_mode='HTML')
        await update.message.reply_text(f"✅ {result_msg}", reply_markup=await keyboards.get_main_menu(uid, (await context.bot.get_me()).username))
    else:
        # 4. فشل التفعيل وتطبيق العقوبة التصاعدية
        is_blocked, block_msg, current_f = log_failed_attempt(uid)
        
        if is_blocked:
            admin_alert = (f"🚫 <b>عقوبة أمنية تلقائية</b>\n"
                           f"👤 المستخدم: <code>{uid}</code>\n"
                           f"⚠️ السبب: تخمين كود\n"
                           f"ℹ️ النتيجة: {block_msg}")
            await context.bot.send_message(chat_id=config.ADMIN_ID, text=admin_alert, parse_mode='HTML')
            await update.message.reply_text(block_msg, parse_mode='HTML')
        else:
            await update.message.reply_text(f"❌ كود غير صحيح. متبقي لك <b>{3-current_f}</b> محاولات قبل الإيقاف.", parse_mode='HTML')
