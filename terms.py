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
    context.user_data['selected_lang'] = user_lang
    chat_id = update.effective_chat.id
    
    # جلب النص من i18n
    terms_text = i18n.get_text('terms_body', lang=user_lang)
    
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
    
    user_lang = context.user_data.get('selected_lang', 'ar')
    
    if query.data == "accept_terms":
        # 1. إظهار نص النجاح
        success_text = i18n.get_text('accept_msg', lang=user_lang)
        
        # تحسين: نحدث الرسالة ونعلم المستخدم أننا نتحقق من اشتراكه
        wait_msg = f"{success_text}\n\n⏳ <b>جاري التحقق من الاشتراك...</b>" if user_lang == 'ar' else f"{success_text}\n\n⏳ <b>Verifying subscription...</b>"
        await query.edit_message_text(wait_msg, parse_mode=ParseMode.HTML)
        
        # 2. الاستدعاء الآمن لملف main
        try:
            from main import check_activation_logic
            # الاستدعاء الآن متوافق مع التعديل اللي سويناه في main.py
            await check_activation_logic(update, context, user_lang=user_lang)
        except Exception as e:
            print(f"CRITICAL ERROR in terms.py: {e}")
            # في حال حدث خطأ تقني، نحاول نفتح القائمة للأمان
            from main import start
            await start(update, context)

    elif query.data == "decline_terms":
        decline_text = i18n.get_text('decline_msg', lang=user_lang)
        await query.edit_message_text(decline_text, parse_mode=ParseMode.HTML)
