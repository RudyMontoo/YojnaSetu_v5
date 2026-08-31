import { useRef, useMemo, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { getTheme } from "../lib/theme";

// Scroll-Driven Mandala Flythrough — per the research spec:
//   • camera travels along the Z-AXIS through the open centers of stacked
//     rings (not a vertical tower) — rings pass around/behind with real occlusion
//   • two-act timeline scrubbed to the hero's scroll range: act 1 moves the
//     key light across; act 2 adds a gentle camera yaw while passing the
//     deeper rings
// `progress()` returns 0..1 for the hero section's own scroll range.

// Colors are plain THREE.Color hex strings, not CSS custom properties, so
// they can't inherit the [data-theme] cascade — each palette is tuned by
// hand per theme instead. The dark palette is deliberately muted (low
// contrast against near-black reads as ceremonial glow); against the light
// theme's cream background those same muted browns nearly disappear, so
// light mode reuses the brand's navy+saffron pairing for real contrast.
const PALETTES = {
  dark: { gold: "#b9852f", saffron: "#9c4f2c", fog: "#08090f", fogNear: 5, fogFar: 19, ambient: 0.16, glass: false },
  // Light mode additionally swaps the solid metallic rings for a translucent
  // glass material (meshPhysicalMaterial + transmission) — solid opaque brown
  // shapes read as clutter over a cream page; a glass motif lets the page
  // show through while still catching the saffron/navy accent color.
  light: { gold: "#e0551f", saffron: "#1a2f4d", fog: "#faf8f4", fogNear: 4, fogFar: 15, ambient: 0.65, glass: true },
};

function useThemePalette() {
  const [theme, setThemeState] = useState(getTheme());
  useEffect(() => {
    const onChange = (e) => setThemeState(e.detail);
    window.addEventListener("yojna-theme-change", onChange);
    return () => window.removeEventListener("yojna-theme-change", onChange);
  }, []);
  return PALETTES[theme] || PALETTES.dark;
}

const RING_GAP = 3.2;
const POOL = 10;                                   // rings alive at once
const RADII = [3.0, 2.5, 2.8, 2.4, 2.7, 2.2, 2.9, 2.3, 2.6, 2.45];

function Ring({ index, r, groupRef, gold, saffron, glass }) {
  const spin = useRef();
  // sun/surya form: torus core + triangular rays radiating outward
  const rays = useMemo(() => {
    const n = 16;
    return Array.from({ length: n }, (_, i) => {
      const a = (i / n) * Math.PI * 2;
      const long = i % 2 === 0;
      return { a, long };
    });
  }, []);
  const marks = useMemo(() => {
    const n = 12 + (index % 3) * 4;
    return Array.from({ length: n }, (_, i) => {
      const a = (i / n) * Math.PI * 2;
      return [Math.cos(a) * r, Math.sin(a) * r, a];
    });
  }, [index, r]);
  useFrame((_, dt) => {
    // continuous CLOCKWISE spin (as seen by the camera looking down -Z)
    if (spin.current) spin.current.rotation.z -= dt * (0.12 + (index % 3) * 0.05);
  });
  return (
    <group ref={groupRef} position-z={-index * RING_GAP}>
      <group ref={spin}>
        <mesh>
          <torusGeometry args={[r, 0.07, 8, 64]} />
          {glass ? (
            <meshPhysicalMaterial color={index % 2 ? saffron : gold} roughness={0.12} metalness={0}
              transmission={0.82} thickness={0.6} ior={1.4} transparent opacity={0.6}
              emissive={index % 2 ? saffron : gold} emissiveIntensity={0.08} />
          ) : (
            <meshStandardMaterial color={index % 2 ? saffron : gold} roughness={0.4} metalness={0.4}
              emissive={index % 2 ? saffron : gold} emissiveIntensity={0.04} />
          )}
        </mesh>
        {/* surya rays — alternating long/short triangular spikes.
            Real `transmission` here would mean up to 160 transmissive
            objects on screen at once (10 rings × 16 rays) — each one forces
            an extra render pass, which is what was actually causing the
            scroll lag, not just the camera smoothing. A plain transparent
            material with a lowered opacity reads as "glass-adjacent" at a
            fraction of the cost, keeping true transmission reserved for the
            one hero element per ring (the torus, below). */}
        {rays.map(({ a, long }, i) => (
          <mesh key={`ray-${i}`}
            position={[Math.cos(a) * (r + (long ? 0.42 : 0.28)), Math.sin(a) * (r + (long ? 0.42 : 0.28)), 0]}
            rotation-z={a - Math.PI / 2}>
            <coneGeometry args={[long ? 0.09 : 0.06, long ? 0.55 : 0.3, 4]} />
            {glass ? (
              <meshStandardMaterial color={long ? gold : saffron} roughness={0.15} metalness={0}
                transparent opacity={0.45} emissive={gold} emissiveIntensity={long ? 0.1 : 0.05} />
            ) : (
              <meshStandardMaterial color={long ? gold : saffron} roughness={0.5} metalness={0.35}
                emissive={gold} emissiveIntensity={long ? 0.12 : 0.05} />
            )}
          </mesh>
        ))}
        {/* carved motif blocks on the ring body — same cost reasoning as the rays above */}
        {marks.map(([x, y, a], i) => (
          <mesh key={i} position={[x, y, 0]} rotation-z={a + Math.PI / 2}>
            <boxGeometry args={i % 4 === 0 ? [0.26, 0.11, 0.15] : [0.13, 0.08, 0.09]} />
            {glass ? (
              <meshStandardMaterial color={i % 4 === 0 ? gold : saffron} roughness={0.15} metalness={0}
                transparent opacity={0.4} />
            ) : (
              <meshStandardMaterial color={i % 4 === 0 ? gold : saffron} roughness={0.55} metalness={0.3} />
            )}
          </mesh>
        ))}
      </group>
    </group>
  );
}

const SCROLL_DEPTH = 46;                            // units of travel across a full page scroll

function Scene({ progress }) {
  const { gold, saffron, fog, fogNear, fogFar, ambient, glass } = useThemePalette();
  const light = useRef();
  const ringRefs = useRef([]);
  useFrame(({ camera, pointer, clock }) => {
    // distance travelled: scroll-driven (Home) or a slow breathing drift (other
    // pages) — the drift stays near the tunnel mouth so the view matches Home's
    // full concentric sun (flying continuously kept a single giant ring in-face)
    const dist = progress
      ? THREE.MathUtils.clamp(progress(), 0, 1) * SCROLL_DEPTH
      : 1.4 + Math.sin(clock.elapsedTime * 0.07) * 1.3;
    const targetZ = 2.4 - dist;
    // 0.09 gave a cinematic trailing feel but visibly lagged behind fast
    // scroll flicks — 0.18 tracks noticeably tighter while still easing
    // instead of snapping. Same value for both themes; this isn't a
    // theme-specific concern.
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.18);
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, pointer.x * 0.3, 0.05);
    camera.position.y = THREE.MathUtils.lerp(camera.position.y, pointer.y * 0.2, 0.05);
    camera.rotation.x = THREE.MathUtils.lerp(camera.rotation.x, -pointer.y * 0.03, 0.05);

    // ♾ infinite tunnel: recycle rings around the camera in both directions
    const span = POOL * RING_GAP;
    ringRefs.current.forEach((g) => {
      if (!g) return;
      while (g.position.z > camera.position.z + RING_GAP) g.position.z -= span;
      while (g.position.z < camera.position.z - span + RING_GAP) g.position.z += span;
    });

    // warm key light sweeps side to side as you travel, always near the camera
    const sweep = Math.sin(dist * 0.35);
    if (light.current) {
      light.current.position.set(sweep * 2.2, 1.6 + Math.cos(dist * 0.2) * 0.8, camera.position.z - 1.5);
    }
  });
  return (
    <>
      <fog attach="fog" args={[fog, fogNear, fogFar]} />
      <ambientLight intensity={ambient} />
      <pointLight ref={light} color={gold} intensity={14} distance={9} decay={2} position={[2.2, 2.5, 1]} />
      {Array.from({ length: POOL }, (_, i) => (
        <Ring key={i} index={i} r={RADII[i % RADII.length]} gold={gold} saffron={saffron} glass={glass}
          groupRef={(el) => { ringRefs.current[i] = el; }} />
      ))}
    </>
  );
}

export default function MandalaTower3D({ height = 420, progress }) {
  return (
    <div style={{ height, width: "100%" }} aria-hidden="true">
      <Canvas
        dpr={[1, 1.5]}
        camera={{ position: [0, 0, 2.4], fov: 52 }}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      >
        <Scene progress={progress} />
      </Canvas>
    </div>
  );
}
