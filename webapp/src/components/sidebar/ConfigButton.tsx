import React from 'react';

interface ConfigButtonProps {
  icon: string;
  label: string;
  value: string;
  onClick: () => void;
}

export default function ConfigButton({ icon, label, value, onClick }: ConfigButtonProps) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between p-3 rounded-lg bg-[#1C1C1E] border border-[#2C2C2E] hover:border-[#0A84FF]/50 transition-all group"
    >
      <div className="flex items-center gap-3">
        <span className="text-xl">{icon}</span>
        <div className="text-left">
          <div className="text-[10px] text-white/40 uppercase tracking-wider font-semibold">
            {label}
          </div>
          <div className="text-sm text-white font-medium">
            {value}
          </div>
        </div>
      </div>
      <svg
        className="w-4 h-4 text-white/20 group-hover:text-white/50 transition-colors"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      </svg>
    </button>
  );
}
