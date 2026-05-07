from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

def get_back_home():
    """زر العودة الموحد"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية"""
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄  تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 اضافة قناة", callback_data='add_channel'), InlineKeyboardButton("حذف /قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐  رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز امان جديد", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    # التأكد من مقارنة الأرقام بشكل صحيح
    if int(uid) == int(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    """
    عرض القنوات مع تجنب مشكلة الـ 64 بايت.
    نستخدم معرف القناة (ID) المختصر أو الفهرس إذا كان الـ ID طويلاً جداً.
    """
    keyboard = []
    
    if entities:
        for entity in entities:
            # بما أننا نستخدم RealDictCursor، البيانات تأتي كقاموس
            name = entity.get('entity_name') or "قناة"
            eid = entity.get('entity_id')
            
            # نرسل d_ متبوعة بالـ ID (معرف التلجرام عادة لا يتجاوز الحد المسموح)
            keyboard.append([InlineKeyboardButton(f"❌ {name}", callback_data=f"d_{eid}")])
            
    keyboard.append([InlineKeyboardButton("➕ إضافة قناة جديدة", callback_data="add_channel")])
    keyboard.append([InlineKeyboardButton("🏠 عودة", callback_data='home')])
    return InlineKeyboardMarkup(keyboard)

def get_request_channel_keyboard():
    """كيبورد طلب اختيار القناة من القائمة (يظهر أسفل الشاشة)"""
    keyboard = [
        [
            KeyboardButton(
                "📢 اضغط هنا لاختيار القناة",
                request_chat=KeyboardButtonRequestChat(
                    request_id=1,
                    chat_is_channel=True,
                    user_administrator_rights={"can_post_messages": True}
                )
            )
        ],
        [KeyboardButton("🔙 إلغاء")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_admin_keyboard():
    """لوحة تحكم الأدمن المحدثة"""
    kb = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data='adm_s'),
            InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')
        ],
        [InlineKeyboardButton("🔑 توليد أكواد تفعيل", callback_data='adm_g')],
        [InlineKeyboardButton("🏠 العودة للرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)
