import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

def get_terms_keyboard(lang='ar'):
    """توليد أزرار الموافقة/الرفض بناءً على اللغة"""
    if lang == 'en':
        keyboard = [[
            InlineKeyboardButton("✅ Agree & Pledge", callback_data="accept_terms"),
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
    
    if user_lang == 'ar':
        terms_text = (
            "⚖️ <b>اتفاقية استخدام نظام سمو الأرقام</b>\n\n"
            "أتعهد أنا المستخدم بالالتزام بالضوابط التالية:\n"
            "1️⃣ عدم استخدام البوت في أي أغراض مخالفة للقوانين.\n"
            "2️⃣ الحفاظ على سرية الرموز (Secret Tokens) الخاصة بي.\n"
            "3️⃣ <b>يمنع منعاً باتاً إعادة بيع الإشارات أو استغلالها تجارياً لأطراف أخرى.</b>\n"
            "4️⃣ البوت وسيلة تقنية للربط فقط، ولا نتحمل مسؤولية قرارات التداول.\n\n"
            "<b>هل توافق على الشروط وتتعهد بالالتزام؟</b>"
        )
    else:
        terms_text = (
            "⚖️ <b>Sumou Signals Terms of Service</b>\n\n"
            "I pledge to adhere to the following guidelines:\n"
            "1️⃣ Not to use the bot for any illegal purposes.\n"
            "2️⃣ To maintain the confidentiality of my Secret Tokens.\n"
            "3️⃣ <b>Strictly prohibited to resell signals or exploit them commercially for third parties.</b>\n"
            "4️⃣ The bot is a technical link only; we are not responsible for trading decisions.\n\n"
            "<b>Do you agree and pledge to comply?</b>"
        )

    if update.callback_query:
        await update.callback_query.edit_message_text(terms_text, reply_markup=get_terms_keyboard(user_lang), parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(terms_text, reply_markup=get_terms_keyboard(user_lang), parse_mode=ParseMode.HTML)

async def handle_terms_callback(update, context, next_step_function):
    """
    معالجة التفاعل مع الأزرار
    :param next_step_function: الدالة التي سيتم استدعاؤها بعد الموافقة (check_activation_logic)
    """
    query = update.callback_query
    user_lang = context.user_data.get('selected_lang', 'ar')
    
    if query.data == "accept_terms":
        # 1. إظهار رسالة انتظار سريعة
        wait_text = "✅ تم قبول الشروط. جاري التحقق..." if user_lang == 'ar' else "✅ Terms Accepted. Verifying..."
        await query.edit_message_text(wait_text, parse_mode=ParseMode.HTML)
        
        # 2. تشغيل الدالة القادمة (اللي مررناها من ملف main)
        await next_step_function(update, context)
        
    elif query.data == "decline_terms":
        decline_text = "🚫 نعتذر، يجب الموافقة على الشروط لاستخدام خدمات البوت." if user_lang == 'ar' else "🚫 Sorry, you must agree to the terms."
        await query.edit_message_text(decline_text, parse_mode=ParseMode.HTML)
