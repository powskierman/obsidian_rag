import React, { useState, useEffect } from 'react';

const STEPS = [
    "Analyzing Query...",
    "Planning Search Strategy...",
    "Searching Vault...",
    "Retrieving Context...",
    "Connecting Entities...",
    "Synthesizing Answer..."
];

export default function ThinkingIndicator({ message }: { message?: string }) {
    const [step, setStep] = useState(0);

    useEffect(() => {
        if (message) return; // Don't cycle if static message provided
        const interval = setInterval(() => {
            setStep((prev) => (prev + 1) % STEPS.length);
        }, 2000);
        return () => clearInterval(interval);
    }, [message]);

    return (
        <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/10">
            <div className="relative w-4 h-4">
                <div className="absolute inset-0 rounded-full border-2 border-[#0A84FF] border-r-transparent animate-spin" />
            </div>
            <span className="text-sm font-medium text-white/70">{message || STEPS[step]}</span>
        </div>
    );
}
