import React, { useEffect } from 'react';
import Header from './components/Header';
import SettingsForm from './components/SettingsForm';
import './index.css';

function App() {
  // كود تهيئة تليجرام لفتح التطبيق بشاشة كاملة وضبط الألوان
  useEffect(() => {
    if (window.Telegram && window.Telegram.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand(); // يفتح التطبيق بكامل شاشة تليجرام
      tg.setHeaderColor('#000000'); // يجعل لون شريط تليجرام أسود
      tg.setBackgroundColor('#000000'); // يجعل لون خلفية التطبيق أسود
    }
  }, []);

  return (
    // الخلفية سوداء، النص أبيض، مع استخدام خط عصري
    <div className="min-h-screen bg-black text-white font-sans antialiased p-4 transition-colors duration-300" dir="rtl">
      {/* حاوية مركزية لتجميع العناصر */}
      <div className="max-w-md mx-auto space-y-8 flex flex-col items-center">
        <Header />
        <SettingsForm />
        
        {/* زر إغلاق التطبيق في الأسفل بشكل أنيق */}
        <div className="text-center pt-6 pb-4 w-full">
          <button 
            onClick={() => window.Telegram.WebApp.close()}
            className="text-[12px] text-gray-500 uppercase tracking-widest border-b border-gray-800 hover:border-gray-600 transition-colors"
          >
            إغلاق التطبيق
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
