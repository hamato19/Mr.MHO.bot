import React from 'react';
import Header from './components/Header';
import SettingsForm from './components/SettingsForm';

function App() {
  return (
    // استخدام flex و items-center لجعل العناصر في المنتصف
    <div className="min-h-screen bg-black text-white flex flex-col items-center p-6 font-sans">
      <div className="w-full max-w-md space-y-8">
        <Header />
        <SettingsForm />
        
        <div className="text-center pt-10">
          <button 
            onClick={() => window.Telegram.WebApp.close()}
            className="text-[12px] text-gray-500 underline uppercase tracking-widest"
          >
            إغلاق التطبيق
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
