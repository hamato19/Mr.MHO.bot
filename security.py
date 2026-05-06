# security.py
import time
import hashlib
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
import logging

# قاموس لتخزين محاولات المستخدمين (Rate Limiting)
user_attempts = {}

def rate_limit(seconds=2):
    """منع المستخدم من إرسال رسائل متتالية بسرعة فائقة (Anti-Spam)"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.effective_user:
                return
            
            uid = update.effective_user.id
            now = time.time()
            
            if uid in user_attempts:
                last_time = user_attempts[uid]
                if now - last_time < seconds:
                    # إذا كان يحاول بسرعة، نتجاهل الرسالة أو نرسل تنبيه بسيط
                    return 
            
            user_attempts[uid] = now
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

def sanitize_input(text):
    """تنظيف المدخلات لمنع ثغرات SQL Injection أو النصوص الخبيثة"""
    if not text:
        return ""
    # إزالة المسافات الزائدة والرموز التي قد تستخدم في تخريب الاستعلامات
    forbidden_chars = [";", "--", "'", '"', "/*", "*/"]
    clean_text = text.strip()
    for char in forbidden_chars:
        clean_text = clean_text.replace(char, "")
    return clean_text[:100] # تحديد طول النص بـ 100 حرف كحد أقصى للأمان

def verify_hash(data, received_hash, secret_key):
    """التحقق من سلامة البيانات (Integrity Check) باستخدام HMAC بسيط"""
    expected_hash = hashlib.sha256(f"{data}{secret_key}".encode()).hexdigest()
    return expected_hash == received_hash

def is_safe_url(url, allowed_domain):
    """التأكد من أن الرابط يخص دومينك فقط لمنع ثغرات Redirect"""
    return url.startswith(allowed_domain)
