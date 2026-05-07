# config.py
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env (للتطوير المحلي)
load_dotenv()

# --- إعدادات البوت الأساسية ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
# تأكد من وضع ID صحيح في Render، القيمة الافتراضية 0 قد تسبب مشاكل في الصلاحيات
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# جلب الدومين مع التأكد من إزالة المائل الأخير لضمان سلامة الروابط في services.py
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com").strip('/')

# --- إعدادات قاعدة البيانات ---
DATABASE_URL = os.getenv('DATABASE_URL')

# --- إعدادات السيرفر ---
# Render يستخدم المنفذ 10000 افتراضياً مع aiohttp، تأكد من مطابقتها في web_server.py
PORT = int(os.environ.get("PORT", 10000))

# --- روابط الدعم والقنوات ---
SUPPORT_LINK = f"tg://user?id={ADMIN_ID}"
