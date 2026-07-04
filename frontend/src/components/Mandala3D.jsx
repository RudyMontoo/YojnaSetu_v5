import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

// Flagship 3D hero moment (design-mythos.md §5.3, §5.5): a layered chakra/
// mandala of low-poly rings + spokes in the existing saffron/gold hues.
// Budget: < 3k triangles, DPR capped, no post-processing, lazy-loaded by the
// caller (React.lazy) so it never blocks first paint. Reduced-motion users
// never mount this — the caller renders the static SVG fallback instead.

const SAFFRON = new THREE.Color("#FF6B35");
const GOLD = new THREE.Color("#F59E0B");

function Ring({ radius, tube, color, speed, tilt }) {
  const ref = useRef();
  useFrame((_, dt) => {
    ref.current.rotation.z += dt * speed;
  });
  return (
    <mesh ref={ref} rotation-x={tilt}>
      <torusGeometry args={[radius, tube, 8, 64]} />
      <meshBasicMaterial color={color} transparent opacity={0.55} />
    </mesh>
  );
}

function Spokes({ count = 24, inner = 0.55, outer = 1.45 }) {
  const ref = useRef();
  const positions = useMemo(() => {
    const arr = [];
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2;
      arr.push({ a, mid: (inner + outer) / 2, len: outer - inner });
    }
    return arr;
  }, [count, inner, outer]);
  useFrame((_, dt) => {
    ref.current.rotation.z -= dt * 0.12;
  });
  return (
    <group ref={ref}>
      {positions.map(({ a, mid, len }, i) => (
        <mesh key={i} position={[Math.cos(a) * mid, Math.sin(a) * mid, 0]} rotation-z={a + Math.PI / 2}>
          <boxGeometry args={[0.018, len, 0.018]} />
          <meshBasicMaterial color={i % 2 ? SAFFRON : GOLD} transparent opacity={i % 2 ? 0.5 : 0.85} />
        </mesh>
      ))}
    </group>
  );
}

function Scene() {
  const group = useRef();
  useFrame(({ pointer }) => {
    // gentle cursor parallax — light is ceremonial, structure utilitarian
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, pointer.y * 0.18, 0.05);
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, pointer.x * 0.25, 0.05);
  });
  return (
    <group ref={group}>
      <Ring radius={1.65} tube={0.012} color={GOLD} speed={0.05} tilt={0} />
      <Ring radius={1.45} tube={0.008} color={SAFFRON} speed={-0.08} tilt={0} />
      <Ring radius={0.55} tube={0.02} color={GOLD} speed={0.15} tilt={0} />
      <Spokes />
      {/* center diya-glow */}
      <mesh>
        <circleGeometry args={[0.16, 24]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.9} />
      </mesh>
      <mesh>
        <circleGeometry args={[0.34, 24]} />
        <meshBasicMaterial color={SAFFRON} transparent opacity={0.12} />
      </mesh>
    </group>
  );
}

export default function Mandala3D({ height = 340 }) {
  return (
    <div style={{ height, width: "100%" }} aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 3.4], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      >
        <Scene />
      </Canvas>
    </div>
  );
}
