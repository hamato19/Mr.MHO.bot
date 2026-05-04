import datetime
from database import get_db # استيراد دالة الاتصال بالقاعدة

async def check_user_access(uid):
    """التحقق هل المستخدم مفعل واشتراكه ساري"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT is_activated, expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            if not user or not user[0]: # is_activated
                return False, "🔒 البوت مغلق. يرجى إرسال رمز التفعيل."
            
            if user[1] and datetime.datetime.now() > user[1]: # expiry_date
                cur.execute("UPDATE users SET is_activated = FALSE WHERE user_id = %s", (str(uid),))
                conn.commit()
                return False, "❌ انتهت فترة اشتراكك. يرجى التجديد."
            
            return True, "مسموح"

async def activate_user_with_code(uid, code):
    """منطق تفعيل الرمز وحرق الكود"""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT duration_days FROM activation_codes WHERE code = %s AND is_used = FALSE", (code,))
            res = cur.fetchone()
            if res:
                days = res[0]
                expiry = datetime.datetime.now() + datetime.timedelta(days=days)
                # تحديث المستخدم
                cur.execute("UPDATE users SET is_activated = TRUE, expiry_date = %s WHERE user_id = %s", (expiry, str(uid)))
                # حرق الرمز
                cur.execute("UPDATE activation_codes SET is_used = TRUE, used_by = %s, used_at = NOW() WHERE code = %s", (str(uid), code))
                conn.commit()
                return True, days
            return False, 0
