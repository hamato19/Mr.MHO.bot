# config.py
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة من ملف .env (للتطوير المحلي فقط)
load_dotenv()

# --- إعدادات البوت الأساسية ---
# يتم جلب التوكن من إعدادات ريندر (Environment Variables)
BOT_TOKEN = os.getenv('BOT_TOKEN')

# معرف الأدمن - القيمة الافتراضية 0 إذا لم يتم ضبطه في ريندر
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# جلب الدومين مع التأكد من إزالة المائل الأخير لضمان سلامة الروابط
DOMAIN = os.getenv('DOMAIN', "https://mr-mho-bot-hewc.onrender.com").strip('/')

# --- إعدادات قاعدة البيانات ---
# الرابط يتم جلبه من متغيرات البيئة في ريندر لضمان السرية والتحكم
DATABASE_URL = os.getenv('DATABASE_URL')

# --- إعدادات السيرفر ---
# المنفذ الذي يستخدمه Render للتشغيل
PORT = int(os.environ.get("PORT", 10000))

# --- روابط الدعم والقنوات ---
SUPPORT_LINK = f"tg://user?id={ADMIN_ID}"
