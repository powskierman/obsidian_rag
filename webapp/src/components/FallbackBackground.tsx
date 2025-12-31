'use client';

export default function FallbackBackground() {
    return (
        <div className="fixed inset-0 overflow-hidden bg-[#0a0a0a] pointer-events-none">
            {/* Animated gradient blobs for ambient lighting */}
            <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-purple-900/30 rounded-full blur-[150px] animate-pulse" style={{ animationDuration: '4s' }} />
            <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-indigo-900/30 rounded-full blur-[150px] animate-pulse" style={{ animationDuration: '5s', animationDelay: '1s' }} />
            <div className="absolute top-1/2 left-1/2 w-[400px] h-[400px] bg-violet-900/25 rounded-full blur-[120px] animate-pulse" style={{ animationDuration: '6s', animationDelay: '2s' }} />
            <div className="absolute top-1/3 right-1/3 w-[350px] h-[350px] bg-fuchsia-900/20 rounded-full blur-[100px] animate-pulse" style={{ animationDuration: '5.5s', animationDelay: '1.5s' }} />

            {/* Enhanced crystalline nodes with larger sizes and stronger glow */}
            {Array.from({ length: 80 }).map((_, i) => {
                const size = Math.random() * 8 + 4; // 4-12px
                const intensity = Math.random();
                return (
                    <div
                        key={i}
                        className="absolute rounded-full animate-pulse"
                        style={{
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                            width: `${size}px`,
                            height: `${size}px`,
                            backgroundColor: `hsl(${270 + Math.random() * 30}, 80%, ${50 + intensity * 20}%)`,
                            boxShadow: `0 0 ${size * 3}px ${size}px hsla(${270 + Math.random() * 30}, 80%, 60%, 0.6)`,
                            animationDelay: `${Math.random() * 3}s`,
                            animationDuration: `${2 + Math.random() * 3}s`,
                        }}
                    />
                );
            })}
        </div>
    );
}
