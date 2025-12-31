'use client';

import { Canvas } from '@react-three/fiber';
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import * as THREE from 'three';

function RotatingCube() {
    const meshRef = useRef<THREE.Mesh>(null);

    useFrame(() => {
        if (meshRef.current) {
            meshRef.current.rotation.x += 0.01;
            meshRef.current.rotation.y += 0.01;
        }
    });

    return (
        <mesh ref={meshRef}>
            <boxGeometry args={[2, 2, 2]} />
            <meshStandardMaterial color="#b026ff" emissive="#b026ff" emissiveIntensity={2} />
        </mesh>
    );
}

export default function SimpleTest3D() {
    console.log('SimpleTest3D rendering');

    return (
        <div className="fixed inset-0 w-full h-full -z-10" style={{ background: '#0a0a0a' }}>
            <Canvas camera={{ position: [0, 0, 5], fov: 75 }}>
                <ambientLight intensity={1} />
                <pointLight position={[10, 10, 10]} intensity={2} />
                <RotatingCube />
            </Canvas>
        </div>
    );
}
