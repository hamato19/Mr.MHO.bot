const SettingsForm = () => {
  // تنسيق مشترك للحقول
  const cardStyle = "w-full bg-[#0a0a0a] border border-gray-900 p-5 rounded-2xl shadow-xl space-y-4";
  const rowStyle = "flex justify-between items-center bg-black/40 p-3 rounded-xl border border-gray-900";
  const inputStyle = "bg-black border border-gray-800 text-[#deff9a] rounded-lg text-center w-16 py-1 focus:border-[#deff9a] outline-none font-bold";

  return (
    <div className="w-full space-y-6">
      {/* قسم إعدادات SMC */}
      <div className={cardStyle}>
        <h3 className="text-[#deff9a] text-[10px] uppercase tracking-widest mb-2 font-bold">إعدادات SMC</h3>
        
        <div className={rowStyle}>
          <span className="text-sm">تفعيل فلتر الموجة</span>
          <input type="checkbox" className="w-5 h-5 accent-[#deff9a]" defaultChecked />
        </div>
        
        <div className={rowStyle}>
          <span className="text-sm">مستوى الفيبوناتشي %</span>
          <input type="number" defaultValue="50" className={inputStyle} />
        </div>
      </div>

      {/* زر التفعيل الرئيسي */}
      <button className="w-full bg-[#deff9a] text-black font-black py-4 rounded-2xl shadow-lg shadow-[#deff9a]/10 hover:scale-[0.98] transition-transform">
        تفعيل التداول الآلي 🔥
      </button>
    </div>
  );
};
