from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- واجهة الخصوصية ---
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق وأرغب بالتفعيل", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# --- واجهة التفعيل والتجديد ---
def get_subscription_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 اشتراك الآن", url="https://sumoualarqam.com/")],
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')]
    ])

# --- القائمة الرئيسية ---
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت مشرف في قناتك", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# --- واجهة اختيار القناة (تفتح القنوات مباشرة) ---
def get_request_channel_keyboard():
    # هذا الزر سيفتح للمستخدم قائمة قنواته التي هو أدمن فيها
    keyboard = [
        [KeyboardButton("📢 اضغط هنا لاختيار القناة وتفويض البوت", request_chat=KeyboardButtonRequestChat(
            request_id=1, 
            chat_is_channel=True, 
            user_administrator_rights={"can_post_messages": True}, # التأكد أن لديه صلاحية النشر
            bot_administrator_rights={"can_post_messages": True}   # طلب صلاحية النشر للبوت
        ))],
        [KeyboardButton("🔙 إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# --- واجهة قنواتي ---
def get_entities_keyboard(entities):
    keyboard = []
    if entities:
        for entity in entities:
            keyboard.append([InlineKeyboardButton(f"❌ حذف: {entity.get('entity_name')}", callback_data=f"del_ch_{entity.get('entity_id')}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_channel")])
    keyboard.append([InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

# --- لوحة الأدمن ---
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]
    ])

def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])
