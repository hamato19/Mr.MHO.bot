import os
import secrets  # المكتبة المسؤولة عن توليد الأكواد العشوائية
import logging
from database import get_db
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# جلب معرف المالك من متغيرات البيئة
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

async def is_owner(uid):
    """التحقق هل المستخدم هو المالك الفعلي"""
    return int(uid) == ADMIN_ID

async def bypass_subscription(uid):
    """تفعيل المالك للأبد في قاعدة البيانات لضمان عدم انقطاع الخدمة عنه"""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET is_activated = TRUE, expiry_date = '2099-01-01' 
                    WHERE user_id = %s
                """, (str(uid),))
                conn.commit()
        return True
    except Exception as e:
        logging.error(f"Owner Bypass Error: {e}")
        return False

async def process_generate_code(update, days):
    """توليد كود اشتراك جديد وحفظه في جدول الأكواد"""
    query = update.callback_query
    
    # توليد كود عشوائي فريد (مثال: MOH-A1B2C3)
    new_code = f"MOH-{secrets.token_hex(3).upper()}" 
    
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # إدخال الكود الجديد في جدول codes
                cur.execute(
                    "INSERT INTO codes (code, duration_days, is_used) VALUES (%s, %s, FALSE)",
                    (new_code, days)
                )
                conn.commit()
        
        txt = (
            f"✅ <b>تم توليد كود جديد بنجاح</b>\n\n"
            f"🔑 الكود: <code>{new_code}</code>\n"
            f"📅 الصلاحية: {days} يوم\n\n"
            f"<i>انسخ الكود وأرسله للمشترك لتفعيل حسابه.</i>"
        )
        
        await query.edit_message_text(
            txt, 
            parse_mode='HTML', 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة للوحة التحكم", callback_data='admin_panel')]])
        )
            
    except Exception as e:
        logging.error(f"Error in process_generate_code: {e}")
        await query.edit_message_text(f"❌ فشل في قاعدة البيانات: {e}")
