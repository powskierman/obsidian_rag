'use client';

export default function FallbackBackground() {
    return (
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
            <div
                className="absolute inset-0"
                style={{
                    backgroundColor: '#0a0a0a',
                    backgroundImage:
                        'radial-gradient(1200px 800px at 15% 20%, rgba(52, 96, 168, 0.28), transparent 60%),' +
                        'radial-gradient(900px 700px at 85% 10%, rgba(138, 78, 210, 0.22), transparent 55%),' +
                        'radial-gradient(1000px 800px at 70% 80%, rgba(12, 126, 158, 0.18), transparent 60%),' +
                        'linear-gradient(180deg, rgba(6, 8, 12, 0.92), rgba(8, 10, 14, 1))'
                }}
            />
            <div className="absolute inset-0 opacity-45">
                <div className="absolute top-[12%] left-[8%] w-[240px] h-[240px] rounded-full border border-[#BFA0FF]/25" />
                <div className="absolute bottom-[16%] right-[10%] w-[320px] h-[190px] rounded-3xl border border-[#7AD3FF]/20 rotate-[-6deg]" />
                <div className="absolute top-[28%] right-[16%] w-[240px] h-[1px] bg-gradient-to-r from-transparent via-[#BFA0FF]/30 to-transparent rotate-[12deg]" />
                <div className="absolute bottom-[34%] left-[14%] w-[210px] h-[1px] bg-gradient-to-r from-transparent via-[#7AD3FF]/25 to-transparent rotate-[-8deg]" />
                <div className="absolute top-[18%] left-[20%] w-[140px] h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent rotate-[32deg]" />
                <div className="absolute top-[42%] left-[28%] w-[200px] h-[1px] bg-gradient-to-r from-transparent via-[#9DE7FF]/20 to-transparent rotate-[-18deg]" />
                <div className="absolute top-[20%] left-[34%] w-2 h-2 rounded-full bg-[#BFA0FF]/35" />
                <div className="absolute top-[32%] left-[26%] w-1.5 h-1.5 rounded-full bg-white/25" />
                <div className="absolute top-[44%] left-[38%] w-1 h-1 rounded-full bg-[#7AD3FF]/25" />
                <div className="absolute top-[58%] left-[24%] w-1.5 h-1.5 rounded-full bg-white/20" />
                <div className="absolute top-[40%] right-[30%] w-2 h-2 rounded-full bg-[#BFA0FF]/25" />
                <div className="absolute bottom-[22%] right-[36%] w-1.5 h-1.5 rounded-full bg-white/20" />
            </div>
            <div
                className="absolute inset-0"
                style={{
                    backgroundImage:
                        'repeating-linear-gradient(0deg, rgba(255,255,255,0.02), rgba(255,255,255,0.02) 1px, transparent 1px, transparent 2px),' +
                        'repeating-linear-gradient(90deg, rgba(255,255,255,0.015), rgba(255,255,255,0.015) 1px, transparent 1px, transparent 2px)',
                    backgroundSize: '2px 2px, 3px 3px',
                    opacity: 0.05
                }}
            />
        </div>
    );
}
