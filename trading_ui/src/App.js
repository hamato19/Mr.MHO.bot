import React, { useEffect } from 'react';
import Header from './components/Header';
import SettingsForm from './components/SettingsForm';

function App() {
  useEffect(() => {
    // تهيئة واجهة تليجرام
    if (window.Telegram && window.Telegram.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand(); // تمديد التطبيق لملء الشاشة
      tg.setHeaderColor('#000000');
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#000000] text-white p-5 font-sans" dir="rtl">
      <div className="max-w-md mx-auto space-y-6 flex flex-col items-center">
        <Header />
        <SettingsForm />
        
        <button 
          onClick={() => window.Telegram.WebApp.close()}
          className="mt-8 text-gray-500 text-xs tracking-widest border-b border-gray-800 pb-1"
        >
          إغلاق التطبيق
        </button>
      </div>
    </div>
  );
}

export default App;
