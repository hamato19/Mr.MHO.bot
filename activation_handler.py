import logging
from datetime import datetime, timedelta
import database 

def process_activation(user_id, code_text):
    """
    المعالج المنفصل لتفعيل الأكواد.
    """
    # 1. تنظيف النص وتحويله لأحرف كبيرة لضمان التطابق مع قاعدة البيانات
    code_text = str(code_text).strip().upper()
    
    try:
        # 2. استدعاء الدالة من ملف database.py
        # تأكد أن دالة activate_user_with_code تحتوي على conn.commit() في نهايتها
        success, message = database.activate_user_with_code(user_id, code_text)
        
        if success:
            logging.info(f"✅ تم التفعيل بنجاح للمستخدم {user_id} باستخدام الكود {code_text}")
            # تم التفعيل بنجاح، ملف main.py سيتولى الآن نقل المستخدم للقائمة
            return True, message
        else:
            logging.warning(f"⚠️ محاولة تفعيل فاشلة: المستخدم {user_id} - الكود {code_text} - السبب: {message}")
            return False, message
            
    except Exception as e:
        logging.error(f"❌ Error in activation_handler: {e}")
        return False, "❌ حدث خطأ فني داخلي، يرجى التواصل مع الدعم."

def get_activation_instruction_text():
    """نص التعليمات الموحد"""
    return (
        "🔄 <b>قسم تفعيل الاشتراك</b>\n\n"
        "من فضلك قم بإرسال كود التفعيل الخاص بك الآن.\n"
        "مثال: <code>SMO-456FC4</code>\n\n"
        "<i>💡 ملاحظة: تأكد من كتابة الكود بشكل صحيح.</i>"
    )
