import React from 'react';

const SettingsForm = () => {
  // تنسيق مشترك لعناوين الأقسام
  const sectionTitleClass = "text-[#deff9a] text-[10px] uppercase tracking-widest flex items-center gap-2 mb-4";
  const titleDotClass = "w-1.5 h-1.5 bg-[#deff9a] rounded-full";

  // تنسيق مشترك لحقول الإدخال النصية
  const inputClass = "bg-black border border-gray-800 text-[#deff9a] rounded-lg text-center font-bold px-3 py-1.5 w-20 focus:outline-none focus:border-[#deff9a] transition-colors";

  // تنسيق مشترك للتبديل (Checkbox)
  const checkboxClass = "form-checkbox h-5 w-5 accent-[#deff9a] rounded transition-transform active:scale-95";

  return (
    <div className="w-full space-y-10">
      {/* بطاقة إعدادات الـ SMC */}
      <div className="bg-[#0a0a0a] border border-gray-900 p-6 rounded-2xl shadow-xl space-y-6">
        <h3 className={sectionTitleClass}><span className={titleDotClass}></span> إعدادات SMC</h3>
        
        <div className="flex justify-between items-center bg-black/40 p-4 rounded-xl border border-gray-900">
          <span className="text-sm font-medium">تفعيل فلتر الموجة السابقة</span>
          <input type="checkbox" className={checkboxClass} defaultChecked />
        </div>
        
        <div className="flex justify-between items-center bg-black/40 p-4 rounded-xl border border-gray-900">
          <span className="text-sm font-medium">مستوى الفيبوناتشي %</span>
          <input type="number" defaultValue="50" className={inputClass} />
        </div>

        <div className="flex justify-between items-center bg-black/40 p-4 rounded-xl border border-gray-900">
          <span className="text-sm font-medium">قاعدة 1: سحب السيولة</span>
          <input type="checkbox" className={checkboxClass} defaultChecked />
        </div>
      </div>

      {/* بطاقة إعدادات التداول الآلي */}
      <div className="bg-[#0a0a0a] border border-gray-900 p-6 rounded-2xl shadow-xl space-y-6">
        <h3 className={sectionTitleClass}><span className={titleDotClass}></span> إعدادات التداول الآلي</h3>
        
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-gray-100">عدد الإشارات لكل مستوى</span>
          <input type="number" defaultValue="2" className={inputClass} />
        </div>

        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-gray-100">عدد الأيام بين الإشارات</span>
          <input type="number" defaultValue="1" className={inputClass} />
        </div>
      </div>

      {/* زر التفعيل الرئيسي بشكل جذاب */}
      <div className="pt-4">
        <button className="w-full bg-[#deff9a] text-black font-extrabold py-4 rounded-2xl shadow-lg shadow-[#deff9a]/10 hover:brightness-110 active:scale-[0.97] transition-all duration-150">
          تفعيل التداول الآلي 🔥
        </button>
      </div>
    </div>
  );
};

export default SettingsForm;
