import React from 'react';

const ApiKeys = () => {
  return (
    <div className="p-4 bg-[#0a0a0a] rounded-xl border border-gray-900 mx-4 mt-4">
      <h3 className="text-[10px] text-gray-500 uppercase mb-4 tracking-tighter">إعدادات الربط البرمجي</h3>
      <div className="space-y-3">
        <select className="w-full bg-[#151515] border border-gray-800 p-2 rounded text-xs text-white">
            <option>Binance Futures</option>
            <option>Bybit</option>
        </select>
        <input type="password" placeholder="API KEY" className="w-full bg-[#151515] border border-gray-800 p-2 rounded text-xs text-white placeholder:text-gray-700" />
        <input type="password" placeholder="API SECRET" className="w-full bg-[#151515] border border-gray-800 p-2 rounded text-xs text-white placeholder:text-gray-700" />
      </div>
    </div>
  );
};

export default ApiKeys;
