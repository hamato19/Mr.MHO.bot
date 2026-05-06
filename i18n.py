# i18n.py

STRINGS = {
    'ar': {
        'welcome': "🚀 مرحباً بك {name} في نظام سمو الأرقام",
        'terms_body': "⚠️ <b>إخلاء مسؤولية واتفاقية الاستخدام:</b>\n\n1️⃣ <b>الغرض التعليمي:</b> الإشارات لأغراض تعليمية فقط.\n2️⃣ <b>المخاطرة:</b> التداول ينطوي على مخاطرة عالية.\n3️⃣ <b>المسؤولية:</b> أنت المسؤول الوحيد عن قراراتك.\n\n<b>هل توافق على الشروط للبدء؟</b>",
        'accept_msg': "✅ تم تسجيل موافقتك بنجاح. جاري التحقق من حالة اشتراكك...",
        'decline_msg': "🚫 نعتذر، لا يمكن استخدام البوت دون الموافقة على الشروط.\nأرسل /start للمحاولة مجدداً.",
        'wait_code': "⚠️ الوصول مقيد. يرجى إرسال **كود التفعيل** الخاص بك:",
        'success_act': "✅ تم التفعيل بنجاح لمدة {days} يوم!",
        'spam_alert': "⛔️ <b>تنبيه:</b> تم تجاوز حد الطلبات المسموح به.",
        'banned_msg': "🚫 <b>تم الحظر:</b> حسابك محظور نهائياً من النظام.",
        'db_error': "❌ عذراً، فشل الاتصال بقاعدة البيانات.",
        'home_btn': "🏠 القائمة الرئيسية",
        'back_btn': "🔙 عودة",
        'admin_panel': "👮 لوحة تحكم الإدارة",
    },
    'en': {
        'welcome': "🚀 Welcome {name} to Sumou Al-Arqam System",
        'terms_body': "⚠️ <b>Disclaimer & Terms of Use:</b>\n\n1️⃣ <b>Educational:</b> Signals are for education only.\n2️⃣ <b>Risk:</b> Trading involves high financial risk.\n3️⃣ <b>Responsibility:</b> You are solely responsible for your trades.\n\n<b>Do you agree to these terms to start?</b>",
        'accept_msg': "✅ Your agreement has been recorded. Checking your status...",
        'decline_msg': "🚫 Sorry, the bot cannot be used without agreeing to the terms.\nSend /start to try again.",
        'wait_code': "⚠️ Access restricted. Please send your **activation code**:",
        'success_act': "✅ Activation successful for {days} days!",
        'spam_alert': "⛔️ <b>Action Blocked:</b> Rate limit exceeded.",
        'banned_msg': "🚫 <b>Access Denied:</b> Your account is permanently banned.",
        'db_error': "❌ Sorry, database connection error.",
        'home_btn': "🏠 Main Menu",
        'back_btn': "🔙 Back",
        'admin_panel': "👮 Admin Control Panel",
    }
}

def get_text(key, lang='ar', **kwargs):
    """دالة جلب النص بناءً على مفتاح اللغة مع معالجة الأخطاء"""
    try:
        # جلب القاموس الخاص باللغة، والعودة للعربية إذا كانت اللغة غير مدعومة
        lang_dict = STRINGS.get(lang, STRINGS['ar'])
        # جلب النص بناءً على المفتاح
        text = lang_dict.get(key, f"Missing Key: {key}")
        
        # دمج المتغيرات (مثل الاسم أو عدد الأيام) داخل النص
        return text.format(**kwargs) if kwargs else text
    except Exception as e:
        return f"Error text: {key}"
