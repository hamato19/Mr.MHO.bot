import logging
from telegram import Update
from telegram.ext import ContextTypes

# دالة معالجة الأخطاء
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # طباعة الخطأ في سجلات رندر (Logs) بالتفصيل
    logging.error(f"❌ خطأ غير متوقع: {context.error}")
    
    # محاولة إبلاغ المستخدم بوجود مشكلة فنية
    try:
        if update and isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text="⚠️ <b>عذراً، حدث خطأ فني غير متوقع.</b>\nجاري إبلاغ المطور للفحص.",
                parse_mode='HTML'
            )
    except Exception as e:
        logging.error(f"فشل إرسال رسالة الخطأ للمستخدم: {e}")
