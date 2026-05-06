from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import datetime

async def send_renewal_request(update: Update, context: ContextTypes.DEFAULT_TYPE, user_data=None):
    """
    إرسال رسالة التجديد مع عرض تفاصيل المدة المتبقية
    """
    expiry_date = user_data.get('expiry_date') if user_data else None
    
    if not expiry_date:
        remaining_text = "لا يوجد اشتراك سابق ❌"
    else:
        now = datetime.datetime.now()
        if now > expiry_date:
            diff = now - expiry_date
            remaining_text = f"منتهٍ منذ {diff.days} يوم 🛑"
        else:
            diff = expiry_date - now
            remaining_text = f"{diff.days} يوم و {diff.seconds // 3600} ساعة ✅"

    msg = (
        f"📊 <b>حالة اشتراكك الحالية:</b>\n"
        f"⏳ المدة المتبقية: <code>{remaining_text}</code>\n"
        f"──────────────────\n"
        f"🛑 <b>تنبيه:</b> اشتراكك غير نشط حالياً.\n\n"
        f"للاستمرار في استقبال تنبيهات TradingView، يرجى إرسال <b>كود التفعيل</b> الجديد.\n\n"
        f"💡 يمكنك الحصول على الكود عبر الدعم الفني أدناه."
    )
    
    keyboard = [
        [InlineKeyboardButton("☎️ طلب كود (الدعم الفني)", url=f"tg://user?id={context.bot_data.get('admin_id', '')}")],
        [InlineKeyboardButton("🔄 تحديث الحالة", callback_data='home')]
    ]
    
    context.user_data['state'] = 'WAIT_CODE'
    
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else:
        await update.effective_chat.send_message(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
