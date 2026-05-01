import React, { useEffect } from 'react';
import { Settings, Zap, Shield, BarChart3 } from 'lucide-react';
import Header from './components/Header';

function App() {
  useEffect(() => {
    if (window.Telegram && window.Telegram.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      tg.enableClosingConfirmation();
      tg.setHeaderColor('#000000');
      tg.setBackgroundColor('#000000');
    }
  }, []);

  return (
    <div className="flex flex-col min-h-screen bg-black text-white px-6 py-8 select-none" dir="rtl">
      {/* الترويسة */}
      <Header />

      {/* محتوى الإعدادات بشكل بطاقات زجاجية */}
      <div className="flex-1 space-y-6 mt-8">
        
        {/* قسم إعدادات SMC */}
        <div className="bg-[#0f0f0f] border border-gray-800 rounded-3xl p-5 space-y-5">
          <div className="flex items-center gap-2 text-[#deff9a]">
            <Shield size={18} />
            <h2 className="text-xs font-bold uppercase tracking-widest">إعدادات الحماية SMC</h2>
          </div>

          <div className="space-y-4">
            <div className="flex justify-between items-center bg-black/50 p-4 rounded-2xl border border-gray-900">
              <span className="text-sm text-gray-300 font-medium">فلتر الموجة السابقة</span>
              <input type="checkbox" className="w-6 h-6 accent-[#deff9a] rounded-lg" defaultChecked />
            </div>

            <div className="flex justify-between items-center bg-black/50 p-4 rounded-2xl border border-gray-900">
              <span className="text-sm text-gray-300 font-medium">مستوى الفيبوناتشي</span>
              <div className="flex items-center gap-2">
                <input type="number" defaultValue="50" className="bg-transparent border-b border-gray-700 text-[#deff9a] w-12 text-center font-bold focus:border-[#deff9a] outline-none" />
                <span className="text-gray-500 text-xs">%</span>
              </div>
            </div>
          </div>
        </div>

        {/* زر التفعيل الرئيسي - كبير وعصري في الأسفل */}
        <div className="fixed bottom-8 left-6 right-6">
          <button className="w-full bg-[#deff9a] text-black font-black py-5 rounded-2xl flex items-center justify-center gap-3 active:scale-95 transition-all glow-button">
            <Zap fill="black" size={20} />
            تفعيل التداول الذكي
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
