import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# نص إخلاء المسؤولية الرسمي
TERMS_TEXT = (
    "⚠️ **إخلاء مسؤولية واتفاقية الاستخدام - DigiHub**\n\n"
    "باستخدامك لبوت **Mr.MOH**، فإنك تقر وتوافق على ما يلي:\n\n"
    "1️⃣ **الغرض التعليمي:** الإشارات والتحليلات هي لأغراض تعليمية فقط ولا تعد نصيحة استثمارية.\n"
    "2️⃣ **المخاطرة:** تداول الأسواق المالية ينطوي على مخاطرة عالية، وأنت المسؤول الوحيد عن صفقاتك.\n"
    "3️⃣ **إخلاء المسؤولية:** يخلي مطور البوت مسؤوليته عن أي خسائر مادية قد تنتج عن استخدام البيانات.\n"
    "4️⃣ **الملكية:** يمنع توزيع أو بيع محتوى البوت لأطراف خارجية.\n\n"
    "**هل توافق على هذه الشروط للبدء؟**"
)

def get_terms_keyboard():
    """إنشاء أزرار الموافقة"""
    keyboard = [
        [
            InlineKeyboardButton("✅ أوافق وأتعهد", callback_data="accept_terms"),
            InlineKeyboardButton("❌ لا أوافق", callback_data="decline_terms")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_terms(update, context):
    """دالة إرسال الشروط للمستخدم"""
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=TERMS_TEXT,
        reply_markup=get_terms_keyboard(),
        parse_mode='HTML'
    )

async def handle_terms_callback(update, context):
    """معالجة استجابة المستخدم على الشروط"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "accept_terms":
        await query.edit_message_text(
            "✅ **تم تسجيل موافقتك بنجاح.**\n\n"
            "⚠️ الوصول مقيد. يرجى إرسال **كود التفعيل** الخاص بك للبدء:",
            parse_mode='HTML'
        )
        
    elif query.data == "decline_terms":
        await query.edit_message_text(
            "🚫 **نعتذر، لا يمكن استخدام البوت دون الموافقة على الشروط.**\n\n"
            "إذا غيرت رأيك، يمكنك إرسال /start مرة أخرى.",
            parse_mode='HTML'
        )
