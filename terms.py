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
    """
    معالجة الضغط على أزرار الشروط.
    ملاحظة: المنطق الفعلي للانتقال يفضل أن يكون في handle_callback داخل main.py
    لتجنب مشكلة الـ Circular Import.
    """
    query = update.callback_query
    user_lang = context.user_data.get('selected_lang', 'ar')
    
    if query.data == "accept_terms":
        success_text = i18n.get_text('accept_msg', lang=user_lang)
        # رسالة انتظار احترافية
        wait_text = f"✅ {success_text}\n\n⏳ <b>جاري التحقق من حالة اشتراكك...</b>" if user_lang == 'ar' else f"✅ {success_text}\n\n⏳ <b>Verifying your subscription...</b>"
        await query.edit_message_text(wait_text, parse_mode=ParseMode.HTML)
        
        # ملاحظة لأبو إلياس: الاستدعاء سيتم آلياً من خلال main.py 
        # لأننا ربطنا accept_terms بدالة check_activation_logic هناك.
        
    elif query.data == "decline_terms":
        decline_text = i18n.get_text('decline_msg', lang=user_lang)
        await query.edit_message_text(decline_text, parse_mode=ParseMode.HTML)
