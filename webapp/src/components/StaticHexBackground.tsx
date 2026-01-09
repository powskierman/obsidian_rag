'use client';

import React, { useEffect, useMemo, useState } from 'react';

// Seeded random for consistent result across renders (mock)
const alea = (seed: number) => {
    let s = seed % 2147483647;
    if (s <= 0) s += 2147483646;
    return () => {
        return (s = s * 16807 % 2147483647) / 2147483647;
    };
};

interface Node {
    id: number;
    x: number;
    y: number;
    size: number;
    opacity: number;
    color: string;
}

interface Link {
    source: Node;
    target: Node;
}

export default function StaticHexBackground() {
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    // Generate static graph data once (client-only to avoid hydration mismatch)
    const { nodes, links } = useMemo(() => {
        if (!isMounted) {
            return { nodes: [], links: [] };
        }
        const rng = alea(56789); // New seed for a fresh look
        const nodeList: Node[] = [];
        const linkList: Link[] = [];

        const width = 100; // Viewport percentage
        const height = 100;
        const nodeCount = 45; // Slightly more nodes

        // Generate Nodes
        for (let i = 0; i < nodeCount; i++) {
            nodeList.push({
                id: i,
                x: rng() * width,
                y: rng() * height,
                size: 3 + rng() * 5, // Larger size: 3-8
                opacity: 0.4 + rng() * 0.6, // Much brighter: 0.4 - 1.0
                color: rng() > 0.6 ? '#d28eff' : '#a855f7', // Lighter purples (Obsidian)
            });
        }

        // Generate Links (simple distance based)
        for (let i = 0; i < nodeList.length; i++) {
            for (let j = i + 1; j < nodeList.length; j++) {
                const a = nodeList[i];
                const b = nodeList[j];
                const dx = a.x - b.x;
                const dy = (a.y - b.y) * (16 / 9); // Aspect ratio correction approx
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 22) { // Increased connection threshold for more links
                    linkList.push({ source: a, target: b });
                }
            }
        }

        return { nodes: nodeList, links: linkList };
    }, [isMounted]);

    // Hexagon Path Generator
    const getHexagonPath = (x: number, y: number, r: number) => {
        // Flat-topped hexagon
        const points = [];
        for (let i = 0; i < 6; i++) {
            const angle_deg = 60 * i;
            const angle_rad = Math.PI / 180 * angle_deg;
            points.push(`${x + r * Math.cos(angle_rad)},${y + r * Math.sin(angle_rad)}`);
        }
        return `M${points.join(' L')} Z`;
    };

    return (
        <div className="fixed inset-0 overflow-hidden -z-50 pointer-events-none bg-[#13111c]">
            {/* Lighter, richer gradient background */}
            <div className="absolute inset-0 bg-gradient-to-br from-[#1E1E2E] via-[#13111c] to-[#0a0a0a] opacity-90" />

            {/* Purple ambient glow spots to break up the dark */}
            <div className="absolute top-0 right-0 w-[50vw] h-[50vh] bg-purple-900/10 blur-[120px] rounded-full mix-blend-screen" />
            <div className="absolute bottom-0 left-0 w-[50vw] h-[50vh] bg-indigo-900/10 blur-[120px] rounded-full mix-blend-screen" />

            {/* Static SVG Layer */}
            {isMounted && (
                <svg
                    className="absolute inset-0 w-full h-full"
                    viewBox="0 0 100 100"
                    preserveAspectRatio="none"
                >
                    {/* Defs for Glow Effects */}
                    <defs>
                        <filter id="glow-purple-strong" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur stdDeviation="0.5" result="coloredBlur" />
                            <feMerge>
                                <feMergeNode in="coloredBlur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                    </defs>

                    {/* Links - Brighter and thicker */}
                    {links.map((link, i) => (
                        <line
                            key={`link-${i}`}
                            x1={link.source.x}
                            y1={link.source.y}
                            x2={link.target.x}
                            y2={link.target.y}
                            stroke="#00D1C1"
                            strokeWidth="0.15"
                            strokeOpacity="0.35"
                        />
                    ))}

                    {/* Nodes (Hexagons) */}
                    {nodes.map((node) => (
                        <g key={`node-${node.id}`}>
                            {/* Glow halo */}
                            <path
                                d={getHexagonPath(node.x, node.y, node.size * 0.8 / 3)}
                                fill={node.color}
                                fillOpacity={node.opacity * 0.4}
                                filter="url(#glow-purple-strong)"
                            />
                            {/* Core Hexagon - Lighter stroke */}
                            <path
                                d={getHexagonPath(node.x, node.y, node.size * 0.4 / 3)}
                                fill={node.color}
                                fillOpacity={node.opacity}
                                stroke="#e0c2ff"
                                strokeWidth="0.08"
                                strokeOpacity="0.6"
                            />
                        </g>
                    ))}
                </svg>
            )}
        </div>
    );
}
