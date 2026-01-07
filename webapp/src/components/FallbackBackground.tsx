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
