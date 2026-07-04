import { useRef, useState, useEffect, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line, Billboard, Text } from "@react-three/drei";
import * as THREE from "three";

// The Sabha (design deck §2, Recommended): 12 agent nodes in a royal-council
// circle around the Orchestrator hub. Active agents glow and lift; animated
// light-threads run hub↔agent (and agent↔agent when they collaborate) —
// showing real collaboration patterns, not a status list. Low-poly, one warm
// key light, camera drift on cursor (camera motion, not object spin).

const GOLD = new THREE.Color("#F59E0B");
const SAFFRON = new THREE.Color("#FF6B35");
const GREEN = new THREE.Color("#22C55E");
const IDLE = new THREE.Color("#3a3d52");

export const SABHA_AGENTS = [
  "Eligibility", "Discovery", "Guidance", "Document", "Grievance", "Nudge",
  "Financial", "Comparison", "CSC", "Analytics", "Biometric", "Offline Proof",
];

// choreography: [activeIds, collaboration pairs] — mirrors real orchestrator
// flows (eligibility→discovery, financial+comparison in parallel, etc.)
const DEMO = [
  { active: [0], links: [[-1, 0]] },
  { active: [1], links: [[-1, 1], [0, 1]] },
  { active: [6, 7], links: [[-1, 6], [-1, 7], [6, 7]] },
  { active: [3], links: [[-1, 3]] },
  { active: [], links: [], done: true },
];

const RADIUS = 2.05;

function nodePos(i) {
  const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
  return [Math.cos(a) * RADIUS, 0, Math.sin(a) * RADIUS];
}

function AgentNode({ index, name, active, done }) {
  const mesh = useRef();
  const mat = useRef();
  const target = active ? 0.35 : 0;
  useFrame((state, dt) => {
    mesh.current.position.y = THREE.MathUtils.lerp(mesh.current.position.y, target, 0.1);
    const color = active ? SAFFRON : done ? GREEN : IDLE;
    mat.current.color.lerp(color, 0.08);
    mat.current.emissive.lerp(active ? GOLD : done ? GREEN : new THREE.Color("#000000"), 0.08);
    if (active) mesh.current.rotation.y += dt * 1.2;
  });
  const [x, , z] = nodePos(index);
  return (
    <group position={[x, 0, z]}>
      <mesh ref={mesh} castShadow>
        <icosahedronGeometry args={[0.17, 0]} />
        <meshStandardMaterial ref={mat} color={IDLE} roughness={0.35} metalness={0.5}
                              emissive="#000000" emissiveIntensity={0.85} />
      </mesh>
      {/* pillar base */}
      <mesh position={[0, -0.32, 0]}>
        <cylinderGeometry args={[0.045, 0.07, 0.34, 6]} />
        <meshStandardMaterial color="#1a1c2e" roughness={0.8} />
      </mesh>
      <Billboard position={[0, 0.62, 0]}>
        <Text fontSize={0.135} color={active ? "#F59E0B" : "#8a8da3"} anchorX="center"
              outlineWidth={0.004} outlineColor="#08090f">
          {name}
        </Text>
      </Billboard>
    </group>
  );
}

function Thread({ from, to }) {
  const ref = useRef();
  const points = useMemo(() => {
    const a = new THREE.Vector3(...(from === -1 ? [0, 0.15, 0] : nodePos(from)));
    const b = new THREE.Vector3(...(to === -1 ? [0, 0.15, 0] : nodePos(to)));
    if (from !== -1) a.y = 0.15;
    if (to !== -1) b.y = 0.15;
    const mid = a.clone().lerp(b, 0.5); mid.y += 0.55;   // arc over the floor
    return new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(24);
  }, [from, to]);
  useFrame((state) => {
    if (ref.current) ref.current.material.dashOffset = -state.clock.elapsedTime * 1.6;
  });
  return (
    <Line ref={ref} points={points} color="#F59E0B" lineWidth={1.6}
          dashed dashSize={0.14} gapSize={0.09} transparent opacity={0.9} />
  );
}

function Scene({ step }) {
  const group = useRef();
  const seq = DEMO[step % DEMO.length];
  useFrame(({ camera, pointer }) => {
    // gentle camera drift toward the cursor — the "council chamber" parallax
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pointer.x * 0.9, 0.04);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, 2.3 + pointer.y * 0.35, 0.04);
    camera.lookAt(0, 0.1, 0);
    if (group.current) group.current.rotation.y += 0.0008; // near-imperceptible sabha turn
  });
  return (
    <group ref={group}>
      <fog attach="fog" args={["#08090f", 5, 11]} />
      <ambientLight intensity={0.3} />
      <pointLight color={GOLD} intensity={26} distance={9} decay={2} position={[0, 2.6, 0]} castShadow
                  shadow-mapSize={[512, 512]} />
      {/* council floor: two faint rings */}
      <mesh rotation-x={-Math.PI / 2} position-y={-0.5} receiveShadow>
        <ringGeometry args={[RADIUS - 0.35, RADIUS + 0.35, 48]} />
        <meshStandardMaterial color="#12141f" roughness={0.9} side={THREE.DoubleSide} />
      </mesh>
      <mesh rotation-x={-Math.PI / 2} position-y={-0.49}>
        <ringGeometry args={[RADIUS - 0.02, RADIUS + 0.02, 48]} />
        <meshStandardMaterial color={GOLD} transparent opacity={0.25} side={THREE.DoubleSide} />
      </mesh>
      {/* orchestrator hub */}
      <group>
        <mesh position={[0, 0.15, 0]} castShadow>
          <torusKnotGeometry args={[0.16, 0.05, 48, 8]} />
          <meshStandardMaterial color={GOLD} emissive={GOLD} emissiveIntensity={seq.active.length ? 0.9 : 0.3}
                                roughness={0.3} metalness={0.6} />
        </mesh>
        <Billboard position={[0, -0.22, 0]}>
          <Text fontSize={0.12} color="#F59E0B" anchorX="center">Orchestrator</Text>
        </Billboard>
      </group>
      {SABHA_AGENTS.map((name, i) => (
        <AgentNode key={name} index={i} name={name}
                   active={seq.active.includes(i)} done={seq.done} />
      ))}
      {seq.links.map(([f, t], i) => <Thread key={`${step}-${i}`} from={f} to={t} />)}
    </group>
  );
}

export default function Sabha3D({ height = 380 }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => s + 1), 2400);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ height, width: "100%" }} aria-hidden="true">
      <Canvas
        shadows
        dpr={[1, 1.5]}
        camera={{ position: [0, 2.3, 4.6], fov: 46 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      >
        <Scene step={step} />
      </Canvas>
    </div>
  );
}
