import logging
from datetime import datetime, timedelta
import database 

def process_activation(user_id, code_text):
    """
    المعالج المنفصل لتفعيل الأكواد.
    يستقبل المعرف والنص، ثم يطلب من قاعدة البيانات التحقق والتفعيل.
    """
    # 1. تنظيف النص من أي مسافات زائدة
    code_text = str(code_text).strip()
    
    try:
        # 2. استدعاء الدالة من ملف database.py
        success, message = database.activate_user_with_code(user_id, code_text)
        
        if success:
            logging.info(f"✅ تم التفعيل بنجاح للمستخدم {user_id} باستخدام الكود {code_text}")
            return True, message
        else:
            logging.warning(f"⚠️ محاولة تفعيل فاشلة: المستخدم {user_id} - الكود {code_text}")
            return False, message
            
    except Exception as e:
        logging.error(f"❌ Error in activation_handler: {e}")
        return False, "❌ حدث خطأ فني داخلي، يرجى التواصل مع الدعم."

def get_activation_instruction_text():
    """نص التعليمات الموحد الذي يظهر للمستخدم عند طلب الكود"""
    return (
        "🔄 <b>قسم تفعيل الاشتراك</b>\n\n"
        "من فضلك قم بإرسال كود التفعيل الخاص بك الآن.\n"
        "مثال: <code>SMO-456FC4</code>\n\n"
        "<i>💡 ملاحظة: لا يهم إذا كانت الحروف كبيرة أو صغيرة.</i>"
    )
