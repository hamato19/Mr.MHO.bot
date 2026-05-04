import datetime
from database import get_db  # استدعاء دالة إدارة الاتصال من ملف database.py

async def check_user_access(uid):
    """
    يفحص هل المستخدم مفعل واشتراكه ساري المفعول.
    يتم استدعاء هذه الدالة في كل مرة يتفاعل فيها المستخدم مع البوت.
    """
    with get_db() as conn:
        # استخدام RealDictCursor يجعل الوصول للبيانات باسم العمود (user['expiry_date'])
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT is_activated, expiry_date FROM users WHERE user_id = %s", (str(uid),))
            user = cur.fetchone()
            
            # 1. إذا كان المستخدم غير موجود أو غير مفعل
            if not user or not user['is_activated']:
                return False, "🔒 البوت مغلق. يرجى إرسال رمز التفعيل للمتابعة."
            
            # 2. إذا كان مفعلاً ولكن تاريخ الانتهاء قد مضى
            if user['expiry_date'] and datetime.datetime.now() > user['expiry_date']:
                cur.execute("UPDATE users SET is_activated = FALSE WHERE user_id = %s", (str(uid),))
                conn.commit()
                return False, "❌ انتهت فترة اشتراكك (التجريبية/المدفوعة). يرجى التواصل مع الإدارة للتجديد."
            
            return True, "مسموح"

async def activate_user_with_code(uid, code):
    """
    يتحقق من صحة الرمز المدخل ويقوم بتفعيل المستخدم بناءً على الأيام المحددة في الرمز.
    """
    user_code = code.strip()
    
    with get_db() as conn:
        from psycopg2.extras import RealDictCursor
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # البحث عن الرمز ومدته
            cur.execute("SELECT duration_days FROM activation_codes WHERE code = %s AND is_used = FALSE", (user_code,))
            code_entry = cur.fetchone()
            
            if code_entry:
                days = code_entry['duration_days']
                expiry = datetime.datetime.now() + datetime.timedelta(days=days)
                
                # تحديث حالة المستخدم وتاريخ الانتهاء
                # تم استخدام ON CONFLICT لضمان إنشاء سجل للمستخدم إذا لم يكن موجوداً مسبقاً
                cur.execute("""
                    INSERT INTO users (user_id, is_activated, expiry_date) 
                    VALUES (%s, TRUE, %s)
                    ON CONFLICT (user_id) DO UPDATE SET is_activated = TRUE, expiry_date = %s
                """, (str(uid), expiry, expiry))
                
                # وسم الرمز بأنه مستخدم "حرق الرمز"
                cur.execute("""
                    UPDATE activation_codes 
                    SET is_used = TRUE, used_by = %s, used_at = NOW() 
                    WHERE code = %s
                """, (str(uid), user_code))
                
                conn.commit()
                return True, days
            
            return False, 0
