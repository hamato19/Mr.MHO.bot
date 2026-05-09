import logging
import database 

def process_activation(user_id, code_text):
    """
    معالج التفعيل: وظيفته فقط التحقق من الكود وتحديث قاعدة البيانات.
    يجب ألا يحتوي على أي أوامر إرسال رسائل لتجنب تكرار القوائم.
    """
    # 1. تنظيف النص وتحويله لأحرف كبيرة
    code_text = str(code_text).strip().upper()
    
    try:
        # 2. استدعاء التفعيل من قاعدة البيانات
        # تأكد أن قاعدة البيانات لا تقوم بإرسال رسائل تلجرام داخلها
        success, message = database.activate_user_with_code(user_id, code_text)
        
        if success:
            logging.info(f"✅ تم التفعيل بنجاح: {user_id}")
            # نكتفي بإرجاع النتيجة، و main.py هو المسؤول عن عرض القائمة لمرة واحدة فقط
            return True, message
        else:
            logging.warning(f"❌ فشل التفعيل: {user_id} - السبب: {message}")
            return False, message
            
    except Exception as e:
        logging.error(f"❌ خطأ في activation_handler: {e}")
        return False, "⚠️ حدث خطأ أثناء الاتصال بقاعدة البيانات."

def get_activation_instruction_text():
    """نص التعليمات الثابت"""
    return (
        "🔄 <b>تفعيل الاشتراك</b>\n\n"
        "أرسل الكود الخاص بك الآن لتتمكن من استخدام كافة الميزات."
    )
