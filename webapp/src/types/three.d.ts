import { Object3DNode } from '@react-three/fiber';
import * as THREE from 'three';

declare module '@react-three/fiber' {
    interface ThreeElements {
        line: Object3DNode<THREE.Line, typeof THREE.Line>;
    }
}
