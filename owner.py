import os
from database import get_db

ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

async def is_owner(uid):
    """التحقق هل المستخدم هو المالك الفعلي"""
    return int(uid) == ADMIN_ID

async def bypass_subscription(uid):
    """
    تحديث قاعدة البيانات لضمان أن المالك دائماً مفعل
    حتى لو انتهى التاريخ أو حصلت مشكلة في الجدول
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # تفعيل المالك للأبد (وضع تاريخ في سنة 2099)
                cur.execute("""
                    UPDATE users 
                    SET is_activated = TRUE, expiry_date = '2099-01-01' 
                    WHERE user_id = %s
                """, (str(uid),))
                conn.commit()
        return True
    except Exception as e:
        print(f"Owner Bypass Error: {e}")
        return False
