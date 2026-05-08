from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- 1. واجهة الخصوصية ---
def get_disclaimer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 سياسة الخصوصية", callback_data='view_priv')],
        [InlineKeyboardButton("✅ موافق وأرغب بالتفعيل", callback_data='accept_tos')],
        [InlineKeyboardButton("❌ رفض", callback_data='reject_tos')]
    ])

# --- 2. واجهة التفعيل (بوابة الدخول) ---
def get_subscription_options():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')],
        [InlineKeyboardButton("💳 اشتراك جديد (سمو الأرقام)", url="https://sumoualarqam.com/")]
    ])

# --- 3. القائمة الرئيسية (تم إضافة زر الإضافة كمسرف هنا) ---
async def get_main_menu(uid, bot_username="bot"):
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 إضافة قناة", callback_data='add_channel'), InlineKeyboardButton("📋 قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄توليد رمز الأمان", callback_data='tok')],
        # الزر المطلوب: يقوم بفتح قائمة القنوات لإضافة البوت مباشرة بصلاحية النشر
        [InlineKeyboardButton("🤖 إضافة البوت مشرف في قناتك", url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    
    # إضافة زر الأدمن إذا كان المستخدم هو المالك
    if str(uid) == str(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
        
    return InlineKeyboardMarkup(kb)

# --- 4. واجهة قنواتي ---
def get_entities_keyboard(entities):
    keyboard = []
    if entities:
        for entity in entities:
            keyboard.append([
                InlineKeyboardButton(f"❌ حذف: {entity.get('entity_name')}", callback_data=f"del_ch_{entity.get('entity_id')}")
            ])
    keyboard.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_channel")])
    keyboard.append([InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

# --- 5. زر العودة السريع ---
def get_back_home():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

# --- 6. لوحة الأدمن ---
def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')],
        [InlineKeyboardButton("🔑 توليد أكواد", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]
    ])
