import datetime
from database import get_db
from psycopg2.extras import RealDictCursor

async def check_user_access(uid, admin_id):
    """
    فحص صلاحية المستخدم:
    1. هل هو الأدمن؟ (دخول دائم)
    2. هل حسابه مفعل؟
    3. هل العداد التنازلي أكبر من صفر؟
    """
    if int(uid) == admin_id:
        return True, "مسموح (أدمن)"

    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT is_activated, expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            # إذا لم يوجد مستخدم أو غير مفعل
            if not user or not user['is_activated']:
                return False, "🔒 النظام مغلق. يتطلب تفعيل الكود."
            
            # فحص العداد التنازلي (هل انتهت المدة؟)
            if user['expiry_date'] and datetime.datetime.now() > user['expiry_date']:
                # تحديث قاعدة البيانات لإيقاف التفعيل فوراً عند انتهاء الوقت
                cur.execute("UPDATE users SET is_activated = FALSE WHERE user_id = %s", (str(uid),))
                conn.commit()
                return False, "❌ انتهى اشتراكك (العداد وصل 0). يرجى التجديد."
            
            return True, "مسموح"

async def activate_with_code(uid, code):
    """
    تفعيل الرموز (10, 30, 60, 90 يوم) وحساب تاريخ الانتهاء بدقة
    """
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # البحث عن الكود في جدول activation_codes
            cur.execute("SELECT duration_days FROM activation_codes WHERE code = %s AND is_used = FALSE", (code.strip(),))
            res = cur.fetchone()
            
            if res:
                days = res['duration_days']
                # حساب تاريخ الانتهاء: الوقت الحالي + عدد الأيام من الكود
                expiry = datetime.datetime.now() + datetime.timedelta(days=days)
                
                # 1. تحديث بيانات المستخدم وتفعيل العداد
                cur.execute("""
                    UPDATE users SET is_activated = TRUE, expiry_date = %s 
                    WHERE user_id = %s
                """, (expiry, str(uid)))
                
                # 2. حرق الكود وتسجيل من استخدمه ومتى (للأمان)
                cur.execute("""
                    UPDATE activation_codes SET is_used = TRUE, used_by = %s, used_at = NOW() 
                    WHERE code = %s
                """, (str(uid), code.strip()))
                
                conn.commit()
                return True, days
                
    return False, 0
