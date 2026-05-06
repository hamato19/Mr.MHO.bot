# config.py
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env إذا كان موجوداً (للتطوير المحلي)
load_dotenv()

# --- إعدادات البوت الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com")

# --- إعدادات قاعدة البيانات ---
# Render يوفر DATABASE_URL تلقائياً
DATABASE_URL = os.getenv('DATABASE_URL')

# --- إعدادات السيرفر (Flask) ---
PORT = int(os.environ.get("PORT", 5000))

# --- روابط الدعم والقنوات ---
SUPPORT_LINK = f"tg://user?id={ADMIN_ID}"
# يمكنك إضافة روابط أخرى هنا لتسهيل تعديلها مستقبلاً
