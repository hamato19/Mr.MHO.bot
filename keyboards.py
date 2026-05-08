from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- 1. أزرار الحماية والخصوصية ---

def get_disclaimer_keyboard():
    """أزرار الموافقة على الشروط"""
    keyboard = [
        [InlineKeyboardButton("📜 عرض سياسة الخصوصية", callback_data='view_priv')],
        [
            InlineKeyboardButton("✅ أوافق", callback_data='accept_tos'),
            InlineKeyboardButton("❌ لا أوافق", callback_data='reject_tos')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_options():
    """خيارات الاشتراك والتفعيل"""
    keyboard = [
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')],
        [InlineKeyboardButton("💳 الاشتراك الآن (تواصل مع الإدارة)", url=config.SUPPORT_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_tos():
    keyboard = [[InlineKeyboardButton("⬅️ العودة للموافقة", callback_data='back_tos')]]
    return InlineKeyboardMarkup(keyboard)

# --- 2. القوائم الرئيسية للمستخدم ---

def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية المربوطة بـ main.py"""
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 اضافة قناة", callback_data='add_channel'), InlineKeyboardButton("حذف /قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز أمان", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    # عرض زر لوحة الأدمن للمالك فقط
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    """عرض القنوات للحذف"""
    keyboard = []
    if entities:
        for entity in entities:
            name = entity.get('entity_name') or "قناة"
            eid = entity.get('entity_id')
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"d_{eid}")])
    keyboard.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_channel")])
    keyboard.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

def get_request_channel_keyboard():
    keyboard = [
        [KeyboardButton("📢 اضغط هنا لاختيار القناة", request_chat=KeyboardButtonRequestChat(
            request_id=1, chat_is_channel=True, user_administrator_rights={"can_post_messages": True}))],
        [KeyboardButton("🔙 إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# --- 3. لوحة تحكم الأدمن (المطابقة لـ main.py) ---

def get_admin_keyboard():
    kb = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد تفعيل", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 العودة للرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

def get_users_management_keyboard(users):
    """عرض المستخدمين في لوحة الأدمن"""
    keyboard = []
    for user in users:
        # ملاحظة: في Neon/Postgres نستخدم user_id
        status_icon = "✅" if user.get('is_activated') else "❌"
        uid = user.get('user_id')
        keyboard.append([InlineKeyboardButton(f"{status_icon} ID: {uid}", callback_data=f"view_u_{uid}")])
    
    keyboard.append([InlineKeyboardButton("🔙 عودة للوحة الأدمن", callback_data="adm")])
    return InlineKeyboardMarkup(keyboard)

def get_user_control_keyboard(target_id, is_active):
    """التحكم بمستخدم معين (تم إصلاح callback_data)"""
    toggle_text = "🚫 تعطيل الحساب" if is_active else "✅ تفعيل الحساب"
    action = "deactivate" if is_active else "activate"
    
    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data=f"toggle_u_{action}_{target_id}")],
        [InlineKeyboardButton("🔙 عودة للقائمة", callback_data="adm_u")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_generation_menu():
    kb = [
        [InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'), InlineKeyboardButton("🗓️ 60 يوم", callback_data='gen_60')],
        [InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90'), InlineKeyboardButton("🗓️ سنة كاملة", callback_data='gen_365')],
        [InlineKeyboardButton("🔙 عودة للوحة الأدمن", callback_data='adm')]
    ]
    return InlineKeyboardMarkup(kb)

def get_back_to_admin():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة المالك", callback_data='adm')]])
