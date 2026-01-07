'use client';

export default function FallbackBackground() {
    const noiseDataUrl =
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='2' stitchTiles='stitch'/></filter><rect width='120' height='120' filter='url(%23n)' opacity='0.35'/></svg>";

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
                    backgroundImage: `url("${noiseDataUrl}")`,
                    backgroundSize: '180px 180px',
                    opacity: 0.08,
                    mixBlendMode: 'soft-light'
                }}
            />
        </div>
    );
}
