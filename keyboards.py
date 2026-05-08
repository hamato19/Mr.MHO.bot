from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- القوائم العامة ---
def get_disclaimer_keyboard():
    keyboard = [
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ أوافق", callback_data='accept_tos'), 
         InlineKeyboardButton("❌ أرفض", callback_data='reject_tos')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_options():
    keyboard = [
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')],
        [InlineKeyboardButton("💳 اشتراك جديد", url=config.SUPPORT_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

# --- القائمة الرئيسية (المستخدم) ---
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 رمز الأمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة كمسرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

# --- لوحة الأدمن ---
def get_admin_keyboard():
    kb = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data='adm'), # لتحديث الأرقام
         InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد تفعيل", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 العودة للرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

def get_generation_menu():
    kb = [
        [InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("🗓️ 60 يوم", callback_data='gen_60')],
        [InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90'), InlineKeyboardButton("🗓️ سنة", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة", callback_data='adm')]
    ]
    return InlineKeyboardMarkup(kb)

def get_users_management_keyboard(users):
    keyboard = []
    for user in users:
        status = "✅" if user.get('is_activated') else "❌"
        uid = user.get('user_id')
        keyboard.append([InlineKeyboardButton(f"{status} ID: {uid}", callback_data=f"view_u_{uid}")])
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="adm")])
    return InlineKeyboardMarkup(keyboard)

def get_user_control_keyboard(target_id, is_active):
    toggle_text = "🚫 تعطيل" if is_active else "✅ تفعيل"
    action = "deactivate" if is_active else "activate"
    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data=f"toggle_u_{action}_{target_id}")],
        [InlineKeyboardButton("🔙 عودة", callback_data="adm_u")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_request_channel_keyboard():
    keyboard = [[KeyboardButton("📢 اختر القناة", request_chat=KeyboardButtonRequestChat(1, True, user_administrator_rights={"can_post_messages": True}))], [KeyboardButton("🔙 إلغاء")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
