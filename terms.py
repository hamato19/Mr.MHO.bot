import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import i18n

def get_terms_keyboard(lang='ar'):
    """توليد أزرار الموافقة/الرفض بناءً على اللغة"""
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
    """إرسال نص الشروط والأحكام"""
    # حفظ اللغة في بيانات المستخدم للرجوع لها لاحقاً
    context.user_data['selected_lang'] = user_lang
    
    chat_id = update.effective_chat.id
    
    # جلب النص من ملف i18n
    terms_text = i18n.get_text('terms_body', lang=user_lang)
    
    # محاولة تعديل الرسالة الحالية أو إرسال رسالة جديدة
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=terms_text,
            reply_markup=get_terms_keyboard(user_lang),
            parse_mode=ParseMode.HTML
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=terms_text,
            reply_markup=get_terms_keyboard(user_lang),
            parse_mode=ParseMode.HTML
        )

async def handle_terms_callback(update, context):
    """معالجة الضغط على أزرار الشروط"""
    query = update.callback_query
    await query.answer()
    
    # استرجاع اللغة التي اختارها المستخدم في البداية
    user_lang = context.user_data.get('selected_lang', 'ar')
    
    if query.data == "accept_terms":
        # 1. إظهار نص النجاح/الموافقة
        success_text = i18n.get_text('accept_msg', lang=user_lang)
        await query.edit_message_text(success_text, parse_mode=ParseMode.HTML)
        
        # 2. استدعاء دالة فحص الاشتراك من الملف الرئيسي
        # تم وضع الاستيراد هنا لتجنب التعارض (Circular Import)
        try:
            from main import check_activation_logic
            # تأكد أن دالة check_activation_logic في main.py تقبل user_lang كمتغير اختياري
            await check_activation_logic(update, context, user_lang=user_lang)
        except Exception as e:
            print(f"Error calling check_activation_logic: {e}")

    elif query.data == "decline_terms":
        # إظهار نص الرفض وتوقف العملية
        decline_text = i18n.get_text('decline_msg', lang=user_lang)
        await query.edit_message_text(decline_text, parse_mode=ParseMode.HTML)
