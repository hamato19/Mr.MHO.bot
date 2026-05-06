import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import i18n

def get_terms_keyboard(lang='ar'):
    """توليد الأزرار بناءً على اللغة الممررة"""
    if lang == 'en':
        keyboard = [[
            InlineKeyboardButton("✅ Agree & Proceed", callback_data="accept_terms"),
            InlineKeyboardButton("❌ Decline", callback_data="decline_terms")
        ]]
    else:
        keyboard = [[
            InlineKeyboardButton("✅ أوافق وأتعهد", callback_data="accept_terms"),
            InlineKeyboardButton("❌ أرفض", callback_data="decline_terms")
        ]]
    return InlineKeyboardMarkup(keyboard)

async def send_terms(update, context, user_lang='ar'):
    """إرسال رسالة الشروط مع الأزرار المترجمة بناءً على لغة المستخدم"""
    chat_id = update.effective_chat.id
    
    # جلب نص الشروط من ملف اللغات i18n
    # تأكد من تعريف 'terms_body' في ملف i18n.py
    terms_text = i18n.get_text('terms_body', lang=user_lang)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=terms_text,
        reply_markup=get_terms_keyboard(user_lang),
        parse_mode='HTML'
    )

async def handle_terms_callback(update, context):
    """معالجة استجابة المستخدم (أوافق/أرفض) ودعم اللغتين"""
    query = update.callback_query
    await query.answer()
    
    # تحديد اللغة من بيانات المستخدم اللي ضغط الزر
    lang = query.from_user.language_code
    user_lang = lang if lang in ['ar', 'en'] else 'ar'
    
    if query.data == "accept_terms":
        # 1. تحديث الرسالة لنص النجاح
        success_text = i18n.get_text('accept_msg', lang=user_lang)
        await query.edit_message_text(success_text, parse_mode='HTML')
        
        # 2. استدعاء فحص الاشتراك من الملف الرئيسي
        from main import check_activation_logic
        await check_activation_logic(update, context)
        
    elif query.data == "decline_terms":
        # تحديث الرسالة لنص الرفض
        decline_text = i18n.get_text('decline_msg', lang=user_lang)
        await query.edit_message_text(decline_text, parse_mode='HTML')
