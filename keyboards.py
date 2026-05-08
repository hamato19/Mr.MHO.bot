from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# 1. واجهة الخصوصية
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق وأرغب بالتفعيل", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# 2. واجهة التفعيل والتجديد (تم دمج الأزرار بصف واحد)
def get_subscription_options():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 اشتراك الآن", url="https://sumoualarqam.com/"),
            InlineKeyboardButton("🎫 ادخل كود التفعيل", callback_data='ren')
        ]
    ])

# 3. القائمة الرئيسية
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت مشرف", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    # التأكد من مطابقة الـ ID مع النوع (String أو Int) حسب ملف config
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# 4. لوحة الأدمن
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]
    ])

# 5. قائمة مدد الأكواد
def get_generation_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90')],
        [InlineKeyboardButton("🗓️ سنة كاملة", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة للأدمن", callback_data='adm')]
    ])

# 6. واجهة اختيار القناة (تحسين الخصائص)
def get_request_channel_keyboard():
    keyboard = [
        [KeyboardButton(
            text="📢 اضغط هنا لاختيار القناة", 
            request_chat=KeyboardButtonRequestChat(
                request_id=1, 
                chat_is_channel=True,
                user_administrator_rights={"can_post_messages": True},
                bot_administrator_rights={"can_post_messages": True} # لضمان قدرة البوت على النشر فور إضافته
            )
        )],
        [KeyboardButton(text="🔙 إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])
