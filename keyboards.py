from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- أزرار البداية والخصوصية ---
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ أوافق", callback_data='accept_tos'), 
         InlineKeyboardButton("❌ أرفض", callback_data='reject_tos')]
    ])

def get_subscription_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')],
        [InlineKeyboardButton("💳 اشتراك جديد", url=config.SUPPORT_LINK)]
    ])

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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد تفعيل", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 العودة للرئيسية", callback_data='home')]
    ])

def get_generation_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("🗓️ 60 يوم", callback_data='gen_60')],
        [InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90'), InlineKeyboardButton("🗓️ سنة", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة", callback_data='adm')]
    ])

def get_users_management_keyboard(users):
    keyboard = []
    for user in users:
        status = "✅" if user.get('is_activated') else "❌"
        uid = user.get('user_id')
        keyboard.append([InlineKeyboardButton(f"{status} ID: {uid}", callback_data=f"view_u_{uid}")])
    keyboard.append([InlineKeyboardButton("🔙 عودة", callback_data="adm")])
    return InlineKeyboardMarkup(keyboard)

def get_user_control_keyboard(target_id, is_active):
    toggle_text = "🚫 تعطيل الحساب" if is_active else "✅ تفعيل الحساب"
    action = "deactivate" if is_active else "activate"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"toggle_u_{action}_{target_id}")],
        [InlineKeyboardButton("🔙 عودة", callback_data="adm_u")]
    ])
