'use client';

import React, { useRef, useMemo, useEffect, Suspense } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';

interface GraphNode {
    id: string;
    name: string;
    val: number;
    color?: string;
    x?: number;
    y?: number;
    z?: number;
}

interface GraphLink {
    source: string | GraphNode;
    target: string | GraphNode;
    distance?: number;
}

interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
}

interface KnowledgeGraph3DProps {
    nodeCount?: number;
    data?: GraphData;
}

// Obsidian Crystal Node Component
function ObsidianNode({ position, size, color, onClick }: any) {
    const meshRef = useRef<THREE.Mesh>(null);
    const glowRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current) {
            // Gentle rotation for crystalline effect
            meshRef.current.rotation.y += 0.002;
            meshRef.current.rotation.x += 0.001;

            // Subtle pulsing glow
            const pulse = Math.sin(state.clock.elapsedTime * 0.5) * 0.1 + 0.9;
            if (glowRef.current) {
                glowRef.current.scale.setScalar(pulse);
            }
        }
    });

    const nodeColor = color || '#b026ff';

    return (
        <group position={position} onClick={onClick}>
            {/* Outer Glow */}
            <mesh ref={glowRef} scale={1.8}>
                <icosahedronGeometry args={[size * 1.5, 0]} />
                <meshBasicMaterial
                    color={nodeColor}
                    transparent
                    opacity={0.3}
                    blending={THREE.AdditiveBlending}
                />
            </mesh>

            {/* Main Crystal */}
            <mesh ref={meshRef}>
                <icosahedronGeometry args={[size, 1]} />
                <meshPhysicalMaterial
                    color={nodeColor}
                    transparent
                    opacity={0.9}
                    metalness={0.3}
                    roughness={0.1}
                    clearcoat={1.0}
                    clearcoatRoughness={0.1}
                    transmission={0.3}
                    thickness={0.5}
                    emissive={nodeColor}
                    emissiveIntensity={2.0}
                />
            </mesh>

            {/* Inner Core Glow */}
            <mesh scale={0.6}>
                <icosahedronGeometry args={[size * 0.6, 0]} />
                <meshBasicMaterial
                    color="#ffffff"
                    transparent
                    opacity={1.0}
                    blending={THREE.AdditiveBlending}
                />
            </mesh>
        </group>
    );
}

// Connection Line Component
function ConnectionLine({ start, end }: { start: THREE.Vector3; end: THREE.Vector3 }) {
    const lineRef = useRef<any>(null);

    const points = useMemo(() => [start, end], [start, end]);
    const geometry = useMemo(() => {
        const geom = new THREE.BufferGeometry().setFromPoints(points);
        return geom;
    }, [points]);

    useFrame((state) => {
        if (lineRef.current) {
            const material = lineRef.current.material as THREE.LineBasicMaterial;
            // Pulse effect on connections
            const pulse = Math.sin(state.clock.elapsedTime * 2) * 0.3 + 0.6;
            material.opacity = pulse;
        }
    });

    return (
        // @ts-expect-error - React Three Fiber primitive
        <line ref={lineRef} geometry={geometry}>
            <lineBasicMaterial
                color="#b026ff"
                transparent
                opacity={0.6}
                blending={THREE.AdditiveBlending}
                linewidth={3}
            />
        </line>
    );
}

// Main Graph Scene
function GraphScene({ nodeCount = 80, data }: { nodeCount?: number; data?: GraphData }) {
    const { camera } = useThree();

    // Generate nodes based on data or random
    const nodes = useMemo(() => {
        if (data && data.nodes.length > 0) {
            return data.nodes.map((node) => ({
                id: node.id,
                name: node.name,
                position: new THREE.Vector3(
                    node.x !== undefined ? node.x * 50 : (Math.random() - 0.5) * 100,
                    node.y !== undefined ? node.y * 50 : (Math.random() - 0.5) * 100,
                    node.z !== undefined ? node.z * 50 : (Math.random() - 0.5) * 80
                ),
                size: (node.val || 1) * 0.5,
                color: node.color || '#b026ff',
            }));
        }

        // Default random constellation
        return Array.from({ length: nodeCount }, (_, i) => {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = 40 + Math.random() * 40;

            return {
                id: `node-${i}`,
                name: ``,
                position: new THREE.Vector3(
                    radius * Math.sin(phi) * Math.cos(theta),
                    radius * Math.sin(phi) * Math.sin(theta),
                    radius * Math.cos(phi)
                ),
                size: Math.random() * 0.8 + 0.4,
                color: `hsl(${270 + Math.random() * 30}, 80%, ${50 + Math.random() * 20}%)`,
            };
        });
    }, [nodeCount, data]);

    // Generate connections
    const connections = useMemo(() => {
        if (data && data.links.length > 0) {
            return data.links.map((link) => {
                const sourceNode = nodes.find(n => n.id === (typeof link.source === 'string' ? link.source : link.source.id));
                const targetNode = nodes.find(n => n.id === (typeof link.target === 'string' ? link.target : link.target.id));

                if (sourceNode && targetNode) {
                    return {
                        start: sourceNode.position,
                        end: targetNode.position,
                    };
                }
                return null;
            }).filter(Boolean);
        }

        // Random connections for constellation effect
        const conns = [];
        for (let i = 0; i < nodes.length * 0.6; i++) {
            const source = nodes[Math.floor(Math.random() * nodes.length)];
            const target = nodes[Math.floor(Math.random() * nodes.length)];

            if (source !== target) {
                conns.push({
                    start: source.position,
                    end: target.position,
                });
            }
        }
        return conns;
    }, [nodes, data]);

    // Slow camera orbit
    useFrame((state) => {
        const t = state.clock.elapsedTime * 0.05;
        camera.position.x = Math.sin(t) * 3;
        camera.position.z = Math.cos(t) * 3;
        camera.lookAt(0, 0, 0);
    });

    return (
        <>
            {/* Ambient Purple-Gold Lighting */}
            <ambientLight intensity={0.8} color="#b026ff" />
            <pointLight position={[10, 10, 10]} intensity={2.0} color="#b026ff" />
            <pointLight position={[-10, -10, -10]} intensity={1.5} color="#ffd700" />
            <pointLight position={[0, 20, 0]} intensity={1.8} color="#9d4edd" />

            {/* Nodes */}
            {nodes.map((node) => (
                <ObsidianNode
                    key={node.id}
                    position={node.position}
                    size={node.size}
                    color={node.color}
                />
            ))}

            {/* Connections */}
            {connections.map((conn, idx) => (
                conn && <ConnectionLine key={idx} start={conn.start} end={conn.end} />
            ))}
        </>
    );
}

// Main Component Export
export default function KnowledgeGraph3D({ nodeCount = 80, data }: KnowledgeGraph3DProps) {
    console.log('KnowledgeGraph3D rendering with nodeCount:', nodeCount);

    return (
        <div className="fixed inset-0 w-full h-full -z-10" style={{ background: '#0a0a0a' }}>
            <Canvas
                gl={{
                    antialias: true,
                    alpha: true,
                    powerPreference: 'high-performance',
                }}
                dpr={[1, 2]}
                style={{ width: '100%', height: '100%' }}
            >
                <color attach="background" args={['#0a0a0a']} />
                <fog attach="fog" args={['#0a0a0a', 80, 250]} />

                <PerspectiveCamera makeDefault position={[0, 0, 100]} fov={60} />

                <Suspense fallback={null}>
                    <GraphScene nodeCount={nodeCount} data={data} />
                </Suspense>

                <OrbitControls
                    enableZoom={false}
                    enablePan={false}
                    autoRotate
                    autoRotateSpeed={0.2}
                    maxPolarAngle={Math.PI / 1.5}
                    minPolarAngle={Math.PI / 3}
                />
            </Canvas>
        </div>
    );
}
