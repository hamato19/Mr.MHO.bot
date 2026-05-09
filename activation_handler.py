import logging
from datetime import datetime, timedelta
import database 

def process_activation(user_id, code_text):
    """المعالج المنفصل لتفعيل الأكواد"""
    # تنظيف النص من المسافات
    code_text = code_text.strip()
    
    try:
        # الربط مع قاعدة البيانات
        success, message = database.activate_user_with_code(user_id, code_text)
        
        if success:
            logging.info(f"✅ تم التفعيل بنجاح للمستخدم {user_id}")
            return True, message
        else:
            return False, message
            
    except Exception as e:
        logging.error(f"Error in activation_handler: {e}")
        return False, "❌ حدث خطأ فني، حاول مرة أخرى."

def get_activation_instruction_text():
    """نص التعليمات المحدث"""
    return (
        "🔄 <b>قسم تفعيل الاشتراك</b>\n\n"
        "من فضلك أرسل كود التفعيل الخاص بك الآن.\n"
        "مثال: <code>SMO-XXXXXX</code>\n\n"
        "<i>سيتم قبول الكود سواء كانت الأحرف كبيرة أو صغيرة.</i>"
    )
