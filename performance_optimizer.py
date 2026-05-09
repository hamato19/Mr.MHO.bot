import logging
from telegram import Update

async def quick_callback_response(update: Update):
    """الرد الفوري على تلجرام لإزالة علامة التحميل من الأزرار"""
    if update.callback_query:
        try:
            # إرسال إشارة 'النجاح' للتلجرام فوراً
            await update.callback_query.answer()
        except Exception as e:
            logging.error(f"فشل الرد السريع على الزر: {e}")
