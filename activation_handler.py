import logging
import database 

def process_activation(user_id, code_text):
    """
    المعالج المنفصل لتفعيل الأكواد.
    يجب أن يقتصر دوره على التفعيل فقط دون التدخل في أزرار الواجهة.
    """
    code_text = str(code_text).strip().upper()
    
    try:
        # استدعاء دالة التفعيل من قاعدة البيانات
        # تأكد أن دالة activate_user_with_code لا تغير بيانات القنوات المرتبطة
        success, message = database.activate_user_with_code(user_id, code_text)
        
        if success:
            logging.info(f"✅ تم التفعيل بنجاح للمستخدم {user_id}")
            return True, message
        else:
            return False, message
            
    except Exception as e:
        logging.error(f"❌ Error in activation_handler: {e}")
        return False, "❌ خطأ فني في معالجة التفعيل."

# تأكد أن هذه الدالة لا تحتوي على أي أوامر إخفاء للكيبورد
def get_activation_instruction_text():
    return (
        "🔄 <b>قسم تفعيل الاشتراك</b>\n\n"
        "من فضلك قم بإرسال كود التفعيل الخاص بك الآن.\n"
        "مثال: <code>SMO-456FC4</code>"
    )
