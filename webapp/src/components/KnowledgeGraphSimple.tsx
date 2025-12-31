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
            // More dramatic rotation
            meshRef.current.rotation.y += 0.02;
            meshRef.current.rotation.x += 0.01;

            // Dramatic pulsing effect - larger amplitude
            const pulse = Math.sin(state.clock.elapsedTime * 1.5) * 0.4 + 1.2;
            meshRef.current.scale.setScalar(pulse);

            // Dramatic glow pulse
            if (glowRef.current) {
                const glowPulse = Math.sin(state.clock.elapsedTime * 1.2) * 0.5 + 1.3;
                glowRef.current.scale.setScalar(glowPulse * 1.8);
            }

            // Outer glow breathing effect
            if (outerGlowRef.current) {
                const outerPulse = Math.sin(state.clock.elapsedTime * 0.8) * 0.6 + 1.4;
                outerGlowRef.current.scale.setScalar(outerPulse * 2.2);
            }
        }
    });

    return (
        <group position={position}>
            {/* Outermost glow halo */}
            <mesh ref={outerGlowRef}>
                <icosahedronGeometry args={[0.6, 0]} />
                <meshBasicMaterial
                    color={color}
                    transparent
                    opacity={0.2}
                    depthWrite={false}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Middle glow */}
            <mesh ref={glowRef}>
                <icosahedronGeometry args={[0.45, 0]} />
                <meshBasicMaterial
                    color={color}
                    transparent
                    opacity={0.5}
                    depthWrite={false}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Main crystal */}
            <mesh ref={meshRef}>
                <icosahedronGeometry args={[0.35, 1]} />
                <meshStandardMaterial
                    color={color}
                    emissive={color}
                    emissiveIntensity={8}
                    metalness={0.6}
                    roughness={0.05}
                    transparent
                    opacity={0.95}
                    side={THREE.DoubleSide}
                />
            </mesh>

            {/* Inner bright core - also pulsing */}
            <mesh scale={0.5}>
                <icosahedronGeometry args={[0.2, 0]} />
                <meshBasicMaterial
                    color="#ffffff"
                    transparent
                    opacity={1.0}
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
        if (lineRef.current?.material) {
            // More dramatic pulsing
            const pulse = Math.sin(state.clock.elapsedTime * 3) * 0.5 + 0.7;
            lineRef.current.material.opacity = pulse;
        }
    });

    return (
        // @ts-expect-error - React Three Fiber primitive
        <line ref={lineRef} geometry={geometry}>
            <lineBasicMaterial
                color="#b026ff"
                transparent
                opacity={0.8}
                linewidth={3}
            />
        </line>
    );
}

function GraphScene() {
    const nodes = useMemo(() => {
        const nodeList = [];
        for (let i = 0; i < 60; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = 8 + Math.random() * 6;

            nodeList.push({
                position: [
                    radius * Math.sin(phi) * Math.cos(theta),
                    radius * Math.sin(phi) * Math.sin(theta),
                    radius * Math.cos(phi)
                ] as [number, number, number],
                color: `hsl(${270 + Math.random() * 30}, 80%, ${50 + Math.random() * 20}%)`
            });
        }
        return nodeList;
    }, []);

    const connections = useMemo(() => {
        const conns = [];
        for (let i = 0; i < 40; i++) {
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
            {/* Enhanced lighting for better glow visibility */}
            <ambientLight intensity={2} color="#b026ff" />
            <pointLight position={[15, 15, 15]} intensity={4} color="#b026ff" />
            <pointLight position={[-15, -15, -15]} intensity={3.5} color="#ffd700" />
            <pointLight position={[0, 20, 0]} intensity={3} color="#9d4edd" />
            <pointLight position={[0, -20, 0]} intensity={2.5} color="#c77dff" />

            {/* Debug test cube at center - remove once working */}
            <TestCube />

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
            <Canvas camera={{ position: [0, 0, 20], fov: 60 }}>
                <GraphScene />

                {/* Bloom post-processing for dramatic glow */}
                <EffectComposer>
                    <Bloom
                        intensity={2.0}
                        luminanceThreshold={0.2}
                        luminanceSmoothing={0.9}
                        mipmapBlur
                    />
                </EffectComposer>
            </Canvas>
        </div>
    );
}
