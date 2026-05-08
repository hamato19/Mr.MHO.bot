from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, KeyboardButtonRequestChat
import config

# --- 1. أزرار الحماية والخصوصية (إجبارية للمستخدم الجديد) ---

def get_disclaimer_keyboard():
    """أزرار الموافقة على الشروط والسياسة مع خيار الرفض"""
    keyboard = [
        [InlineKeyboardButton("📜 عرض سياسة الخصوصية", callback_data='view_priv')],
        [
            InlineKeyboardButton("✅ أوافق", callback_data='accept_tos'),
            InlineKeyboardButton("❌ لا أوافق", callback_data='reject_tos')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_subscription_options():
    """خيارات الاشتراك تظهر بعد الموافقة مباشرة"""
    keyboard = [
        [InlineKeyboardButton("🎫 إدخال كود التفعيل", callback_data='ren')],
        [InlineKeyboardButton("💳 الاشتراك الآن (تواصل مع الإدارة)", url=config.SUPPORT_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_tos():
    """العودة من عرض السياسة إلى خيار الموافقة والرفض"""
    keyboard = [[InlineKeyboardButton("⬅️ العودة للموافقة", callback_data='back_tos')]]
    return InlineKeyboardMarkup(keyboard)

# --- 2. القوائم الرئيسية للمستخدم ---

def get_back_home():
    """زر العودة الموحد"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 عودة للرئيسية", callback_data='home')]])

async def get_main_menu(uid, bot_username="bot"):
    """القائمة الرئيسية للمشترك"""
    kb = [
        [InlineKeyboardButton("👤 حسابي", callback_data='acc'), InlineKeyboardButton("🔄 تجديد الاشتراك", callback_data='ren')],
        [InlineKeyboardButton("📢 اضافة قناة", callback_data='add_channel'), InlineKeyboardButton("حذف /قنواتي", callback_data='chs')],
        [InlineKeyboardButton("🌐 رابط الويب هوك", callback_data='wh'), InlineKeyboardButton("🔄 توليد رمز امان جديد", callback_data='tok')],
        [InlineKeyboardButton("🤖 إضافة البوت كمشرف", url=f"https://t.me/{bot_username}?startchannel=true")],
        [InlineKeyboardButton("☎️ الدعم الفني", url=config.SUPPORT_LINK)]
    ]
    if int(uid) == int(config.ADMIN_ID):
        kb.append([InlineKeyboardButton("👮 لوحة الأدمن", callback_data='adm')])
    return InlineKeyboardMarkup(kb)

def get_entities_keyboard(entities):
    """عرض قائمة القنوات المرتبطة لحذفها"""
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
    """زر طلب القناة (Native Telegram UI)"""
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

# --- 3. لوحة تحكم الأدمن (توليد الأكواد بالمدد الزمنية) ---

def get_admin_keyboard():
    """لوحة تحكم الأدمن"""
    kb = [
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data='adm_s'),
            InlineKeyboardButton("👥 إدارة المستخدمين", callback_data='adm_u')
        ],
        [InlineKeyboardButton("🔑 توليد أكواد تفعيل", callback_data='adm_gen_menu')],
        [InlineKeyboardButton("🏠 العودة للرئيسية", callback_data='home')]
    ]
    return InlineKeyboardMarkup(kb)

def get_generation_menu():
    """قائمة اختيار مدة الكود المطلوب توليده"""
    kb = [
        [
            InlineKeyboardButton("🗓️ 30 يوم", callback_data='gen_30'),
            InlineKeyboardButton("🗓️ 60 يوم", callback_data='gen_60')
        ],
        [
            InlineKeyboardButton("🗓️ 90 يوم", callback_data='gen_90'),
            InlineKeyboardButton("🗓️ سنة كاملة", callback_data='gen_365')
        ],
        [InlineKeyboardButton("🔙 عودة للوحة الأدمن", callback_data='adm')]
    ]
    return InlineKeyboardMarkup(kb)
def get_back_to_admin():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة المالك", callback_data='adm')]])

def get_all_users():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # نختار الأعمدة الموجودة فعلياً في جدولك (Neon)
                cur.execute("SELECT user_id, is_activated, expiry_date FROM users ORDER BY created_at DESC LIMIT 50")
                rows = cur.fetchall()
                return rows # سيعود ببياناتك الحالية بدون أخطاء
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return []



def get_users_management_keyboard(users):
    """تحويل قائمة المستخدمين إلى أزرار تفاعلية"""
    keyboard = []
    
    for user in users:
        uid = user['user_id']
        status_icon = "🟢" if user.get('is_activated') else "🔴"
        button_text = f"{status_icon} ID: {uid}"
        
        # التعديل هنا: نغير usr_ إلى view_u_ ليتطابق مع main.py
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_u_{uid}")])
    
    # إضافة زر العودة بلوحة الأدمن
    keyboard.append([InlineKeyboardButton("⬅️ عودة للخلف", callback_data="adm")])
    
    return InlineKeyboardMarkup(keyboard)



