import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import * as d3 from 'd3';

// Dynamically import ForceGraph2D with no SSR to avoid window is not defined errors
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="p-4 text-gray-400">Loading graph visualization...</div>
});

interface GraphNode {
    id: string;
    name: string;
    val: number; // size
    color?: string;
    group?: string;
}

interface GraphLink {
    source: string;
    target: string;
}

interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
}

interface ForceGraphProps {
    data?: GraphData;
    width?: number;
    height?: number;
    onNodeClick?: (node: any) => void;
}

const ForceGraph: React.FC<ForceGraphProps> = ({ data, width = 600, height = 400, onNodeClick }) => {
    const fgRef = useRef<any>(null);
    const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });

    useEffect(() => {
        if (data) {
            setGraphData(data);
        }
    }, [data]);

    useEffect(() => {
        // Apply custom link distance force
        if (fgRef.current) {
            // Distance Force
            fgRef.current.d3Force('link').distance((link: any) => link.distance || 100);

            // Collision Force - Prevent overlap
            // Radius calculation matches the visual pill size approximation (roughly 20-30px radius)
            // We use a safe margin to ensure clear separation
            fgRef.current.d3Force('collide', d3.forceCollide((node: any) => {
                const label = node.name || '';
                // Estimate width based on character count (approx 6px per char) + padding
                const width = (label.length * 6) + 20;
                return width / 2; // Use half width as radius approximation
            }).strength(0.8));

            // Increase charge to spread nodes out more
            fgRef.current.d3Force('charge').strength(-300);

            fgRef.current.d3ReheatSimulation();
        }
    }, [graphData]);

    return (
        <div className="border border-white/10 rounded-xl overflow-hidden glass-panel">
            <ForceGraph2D
                ref={fgRef}
                graphData={graphData}
                width={width}
                height={height}
                backgroundColor="rgba(0,0,0,0)"
                nodeColor={(node: any) => node.color || '#4facfe'}
                linkColor={() => 'rgba(255,255,255,0.2)'}
                nodeRelSize={6}
                onNodeClick={(node) => onNodeClick && onNodeClick(node)}
                autoPauseRedraw={true}
                // Draw label text
                nodeCanvasObject={(node: any, ctx, globalScale) => {
                    if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;
                    const label = node.name;
                    const fontSize = 12 / globalScale;
                    const radius = 6 / globalScale;

                    ctx.beginPath();
                    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
                    ctx.fillStyle = node.color || '#4facfe';
                    ctx.fill();

                    if (globalScale > 0.9) {
                        ctx.font = `${fontSize}px Sans-Serif`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.5);
                        const x = node.x - bckgDimensions[0] / 2;
                        const y = node.y - bckgDimensions[1] / 2;

                        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
                        ctx.fillRect(x, y, bckgDimensions[0], bckgDimensions[1]);

                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillStyle = '#ffffff';
                        ctx.fillText(label, node.x, node.y);

                        node.__bckgDimensions = bckgDimensions;
                    } else {
                        node.__bckgDimensions = [radius * 2, radius * 2];
                    }
                }}
                nodePointerAreaPaint={(node: any, color, ctx) => {
                    ctx.fillStyle = color;
                    const bckgDimensions = node.__bckgDimensions;
                    if (bckgDimensions) {
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, bckgDimensions[0], bckgDimensions[1]);
                    }
                }}

                d3VelocityDecay={0.6}
                d3AlphaDecay={0.08}
                cooldownTicks={60}
                cooldownTime={1500}
                onEngineStop={() => {
                    fgRef.current?.zoomToFit(400);
                    fgRef.current?.pauseAnimation?.();
                }}
            />
        </div>
    );
};


export default ForceGraph;
