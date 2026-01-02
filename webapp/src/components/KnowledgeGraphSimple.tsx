'use client';

import { Canvas, useFrame } from '@react-three/fiber';
import { useRef, useMemo } from 'react';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';

// Debug test cube - visible if scene is working
function TestCube() {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current) {
            meshRef.current.rotation.x += 0.02;
            meshRef.current.rotation.y += 0.02;
        }
    });

    return (
        <mesh ref={meshRef} position={[0, 0, 0]}>
            <boxGeometry args={[1, 1, 1]} />
            <meshBasicMaterial color="hotpink" wireframe />
        </mesh>
    );
}

function FloatingNode({ position, color }: any) {
    const meshRef = useRef<THREE.Mesh>(null);
    const glowRef = useRef<THREE.Mesh>(null);
    const outerGlowRef = useRef<THREE.Mesh>(null);

    useFrame((state) => {
        if (meshRef.current) {
            // Subtle rotation
            meshRef.current.rotation.y += 0.005;
            meshRef.current.rotation.x += 0.003;

            // Subtle pulsing effect - much smaller amplitude
            const pulse = Math.sin(state.clock.elapsedTime * 0.8) * 0.08 + 1.0;
            meshRef.current.scale.setScalar(pulse);

            // Subtle glow pulse - check if ref current exists
            if (glowRef.current) {
                const glowPulse = Math.sin(state.clock.elapsedTime * 0.6) * 0.1 + 1.05;
                glowRef.current.scale.setScalar(glowPulse * 1.2);
            }

            // Subtle outer glow breathing effect - check if ref current exists
            if (outerGlowRef.current) {
                const outerPulse = Math.sin(state.clock.elapsedTime * 0.4) * 0.12 + 1.08;
                outerGlowRef.current.scale.setScalar(outerPulse * 1.4);
            }
        }
    });

    return (
        <group position={position}>
            {/* Outermost glow halo - more subtle and smaller */}
            <mesh ref={outerGlowRef}>
                <icosahedronGeometry args={[0.4, 0]} />
                <meshBasicMaterial
                    color={color}
                    transparent
                    opacity={0.05}
                    depthWrite={false}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Middle glow - more subtle and smaller */}
            <mesh ref={glowRef}>
                <icosahedronGeometry args={[0.3, 0]} />
                <meshBasicMaterial
                    color={color}
                    transparent
                    opacity={0.1}
                    depthWrite={false}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Main crystal - smaller and more transparent */}
            <mesh ref={meshRef}>
                <icosahedronGeometry args={[0.22, 1]} />
                <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={1.5}
                    metalness={0.6}
                    roughness={0.05}
                    transparent
                    opacity={0.5}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Inner bright core - much subtler and smaller */}
            <mesh scale={0.4}>
                <icosahedronGeometry args={[0.12, 0]} />
                <meshBasicMaterial
                    color="#ffffff"
                    transparent
                    opacity={0.25}
                    depthWrite={false}
                />
            </mesh>
        </group>
    );
}

function ConnectionLine({ start, end }: { start: [number, number, number]; end: [number, number, number] }) {
    const lineRef = useRef<any>(null);

    const points = useMemo(() => {
        return [new THREE.Vector3(...start), new THREE.Vector3(...end)];
    }, [start, end]);

    const geometry = useMemo(() => {
        return new THREE.BufferGeometry().setFromPoints(points);
    }, [points]);

    useFrame((state) => {
        // Safety check for lineRef and material
        if (lineRef.current && lineRef.current.material) {
            // Subtle pulsing for connections
            const pulse = Math.sin(state.clock.elapsedTime * 1.5) * 0.15 + 0.25;
            // Ensure opacity property exists before assignment
            if ('opacity' in lineRef.current.material) {
                lineRef.current.material.opacity = pulse;
            }
        }
    });

    return (
        // @ts-expect-error - React Three Fiber primitive
        <line ref={lineRef} geometry={geometry}>
            <lineBasicMaterial
                color="#b026ff"
                transparent
                opacity={0.3}
                linewidth={1}
            />
        </line>
    );
}

function GraphScene() {
    const nodes = useMemo(() => {
        const nodeList = [];
        // Reduced from 60 to 30 nodes for less visual clutter
        for (let i = 0; i < 30; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = 10 + Math.random() * 8; // Pushed further back

            nodeList.push({
                position: [
                    radius * Math.sin(phi) * Math.cos(theta),
                    radius * Math.sin(phi) * Math.sin(theta),
                    radius * Math.cos(phi)
                ] as [number, number, number],
                color: `hsl(${270 + Math.random() * 30}, 60%, ${40 + Math.random() * 15}%)` // Reduced saturation & lightness
            });
        }
        return nodeList;
    }, []);

    const connections = useMemo(() => {
        const conns = [];
        // Reduced from 40 to 20 connections
        for (let i = 0; i < 20; i++) {
            const a = nodes[Math.floor(Math.random() * nodes.length)];
            const b = nodes[Math.floor(Math.random() * nodes.length)];
            if (a !== b) {
                conns.push({ start: a.position, end: b.position });
            }
        }
        return conns;
    }, [nodes]);

    return (
        <>
            {/* Subtle ambient lighting */}
            <ambientLight intensity={0.5} color="#b026ff" />
            <pointLight position={[15, 15, 15]} intensity={1.0} color="#b026ff" />
            <pointLight position={[-15, -15, -15]} intensity={0.8} color="#ffd700" />
            <pointLight position={[0, 20, 0]} intensity={0.6} color="#9d4edd" />
            <pointLight position={[0, -20, 0]} intensity={0.5} color="#c77dff" />

            {nodes.map((node, i) => (
                <FloatingNode key={i} position={node.position} color={node.color} />
            ))}

            {connections.map((conn, i) => (
                <ConnectionLine key={i} start={conn.start} end={conn.end} />
            ))}
        </>
    );
}

export default function KnowledgeGraphSimple() {
    console.log('KnowledgeGraphSimple rendering');

    return (
        <div className="fixed inset-0 w-full h-full -z-10" style={{ background: '#0a0a0a' }}>
            <Canvas
                camera={{ position: [0, 0, 20], fov: 60 }}
                gl={{
                    alpha: true,
                    antialias: true,
                    preserveDrawingBuffer: true
                }}
                onCreated={({ gl }) => {
                    gl.setClearColor('#0a0a0a', 1)
                }}
            >
                <GraphScene />

                {/* Bloom post-processing - very subtle glow */}
                <EffectComposer>
                    <Bloom
                        intensity={0.3}
                        luminanceThreshold={0.7}
                        luminanceSmoothing={0.4}
                        mipmapBlur
                    />
                </EffectComposer>
            </Canvas>
        </div>
    );
}
