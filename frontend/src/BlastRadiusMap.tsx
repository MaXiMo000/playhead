import { useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import {
  forceSimulation,
  forceManyBody,
  forceLink,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
} from "d3-force";
import type { PlayheadEvent } from "./api";
import { COLORS } from "./TimelineCanvas";
import "./BlastRadiusMap.css";

interface GraphNode extends SimulationNodeDatum {
  id: string;
  label: string;
  color: string;
}

type GraphLink = { source: string | GraphNode; target: string | GraphNode };

// Bash calls get their own node ("shell") the same way they get their own
// track in TimelineCanvas -- they have no file_path to key on, but they're
// still a real step in the sequence a "what did this touch next" map needs
// to show.
function nodeKeyFor(ev: PlayheadEvent): string {
  return ev.tool_name === "Bash" ? "\0shell" : (ev.file_path ?? "\0other");
}

function shortLabel(key: string): string {
  if (key === "\0shell") return "shell";
  if (key === "\0other") return "other";
  const parts = key.split(/[/\\]/);
  return parts[parts.length - 1];
}

// The graph isn't a static dependency graph -- there's no such thing from
// tool-call events alone. It's a *traversal* graph: an edge between two
// files means the session moved from one to the other consecutively in
// time, which is exactly the "blast radius" question this map answers --
// what did the agent touch right after this.
function buildGraph(events: PlayheadEvent[]): { nodes: GraphNode[]; links: GraphLink[] } {
  const keys = new Set<string>();
  const firstTool = new Map<string, string>();
  const links: GraphLink[] = [];
  let prevKey: string | null = null;
  for (const ev of events) {
    const key = nodeKeyFor(ev);
    keys.add(key);
    if (!firstTool.has(key)) firstTool.set(key, ev.tool_name);
    if (prevKey && prevKey !== key) {
      links.push({ source: prevKey, target: key });
    }
    prevKey = key;
  }
  const nodes: GraphNode[] = [...keys].map((key) => ({
    id: key,
    label: shortLabel(key),
    color: COLORS[firstTool.get(key) ?? ""] ?? "#8b93a7",
  }));

  // A stable layout computed once up front -- this doesn't need to animate
  // live like a real-time force graph, it just needs a readable starting
  // position, so the simulation is ticked synchronously to convergence
  // rather than driven frame-by-frame.
  const sim = forceSimulation(nodes)
    .force("charge", forceManyBody().strength(-60))
    .force(
      "link",
      forceLink<GraphNode, GraphLink>(links)
        .id((d) => d.id)
        .distance(3.5)
        .strength(0.7),
    )
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide(1.4))
    .stop();
  for (let i = 0; i < 300; i++) sim.tick();

  return { nodes, links };
}

function linkKey(l: GraphLink): string {
  const s = typeof l.source === "string" ? l.source : l.source.id;
  const t = typeof l.target === "string" ? l.target : l.target.id;
  return `${s}->${t}`;
}

function Edge({ from, to }: { from: [number, number, number]; to: [number, number, number] }) {
  const geometry = useMemo(
    () => new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...from), new THREE.Vector3(...to)]),
    [from, to],
  );
  // <lineSegments>, not <line>: JSX resolves `line` to the SVG element's
  // types, which have no `geometry`, and `tsc -b` fails the build. A
  // two-point segment draws exactly the same edge.
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color="#4a5470" transparent opacity={0.55} />
    </lineSegments>
  );
}

// The signature moment: a ring of light expanding outward from whichever
// file the playhead is currently on, looping continuously -- "what this
// touched" felt as a pulse, not read off a static highlighted node.
function PulseRing({ color }: { color: string }) {
  const ref = useRef<THREE.Mesh>(null);
  const startedAt = useRef<number | null>(null);

  useFrame(({ clock }) => {
    const mesh = ref.current;
    if (!mesh) return;
    startedAt.current ??= clock.elapsedTime;
    const elapsed = clock.elapsedTime - startedAt.current;
    const cycle = elapsed % 1.4;
    const scale = 0.4 + cycle * 3;
    mesh.scale.setScalar(scale);
    const material = mesh.material as THREE.MeshBasicMaterial;
    material.opacity = Math.max(0, 0.7 - cycle / 1.4);
  });

  return (
    <mesh ref={ref}>
      <ringGeometry args={[0.75, 1, 32]} />
      <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
    </mesh>
  );
}

function Node({ node, isActive }: { node: GraphNode; isActive: boolean }) {
  return (
    <group>
      {/* Soft halo behind every node, brighter when active -- a cheap
          stand-in for real bloom post-processing that reads well without
          adding a render-pass dependency. */}
      <mesh>
        <sphereGeometry args={[isActive ? 0.85 : 0.5, 16, 16]} />
        <meshBasicMaterial color={node.color} transparent opacity={isActive ? 0.16 : 0.07} depthWrite={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[isActive ? 0.4 : 0.26, 24, 24]} />
        <meshStandardMaterial
          color={isActive ? "#ffffff" : node.color}
          emissive={node.color}
          emissiveIntensity={isActive ? 1.4 : 0.5}
          roughness={0.35}
          metalness={0.1}
        />
      </mesh>
      {isActive && <PulseRing color={node.color} />}
      <Html distanceFactor={12} style={{ pointerEvents: "none" }}>
        <div className={`blast-node-label${isActive ? " blast-node-label-active" : ""}`}>{node.label}</div>
      </Html>
    </group>
  );
}

interface Props {
  events: PlayheadEvent[];
  playheadTs: number;
}

// Leaves room for a label (~1.8 units) beside the outermost node even in a
// panel narrower than it is tall, where the horizontal view is the tighter one.
const FIT_RADIUS = 3.4;

export default function BlastRadiusMap({ events, playheadTs }: Props) {
  const { nodes, links } = useMemo(() => buildGraph(events), [events]);

  const activeKey = useMemo(() => {
    let key: string | null = null;
    for (const ev of events) {
      if (ev.ts_start <= playheadTs) key = nodeKeyFor(ev);
      else break;
    }
    return key;
  }, [events, playheadTs]);

  const positions = useMemo(() => {
    // Shrink (never enlarge) the layout so its farthest node sits inside
    // FIT_RADIUS: the camera frames about 6.5 units either side at this
    // distance and fov, which leaves room for labels at any auto-rotate
    // angle. A fixed 0.35 scale let a larger session's outer nodes and
    // their labels fall off the edge of the panel.
    const reach = Math.max(0, ...nodes.map((n) => Math.hypot(n.x ?? 0, n.y ?? 0)));
    const scale = reach > 0 ? Math.min(0.35, FIT_RADIUS / reach) : 0.35;
    const map = new Map<string, [number, number, number]>();
    for (const n of nodes) map.set(n.id, [(n.x ?? 0) * scale, (n.y ?? 0) * scale, 0]);
    return map;
  }, [nodes]);

  return (
    <div className="blast-radius-map">
      <Canvas camera={{ position: [0, 0, 14], fov: 50 }} gl={{ preserveDrawingBuffer: true, antialias: true }}>
        <fog attach="fog" args={["#0a0c11", 12, 26]} />
        <ambientLight intensity={0.55} />
        <pointLight position={[5, 5, 8]} intensity={0.9} color="#8fb8ff" />
        <pointLight position={[-6, -4, 6]} intensity={0.35} color="#a78bfa" />

        {links.map((l) => {
          const a = positions.get(typeof l.source === "string" ? l.source : l.source.id);
          const b = positions.get(typeof l.target === "string" ? l.target : l.target.id);
          if (!a || !b) return null;
          return <Edge key={linkKey(l)} from={a} to={b} />;
        })}

        {nodes.map((n) => {
          const pos = positions.get(n.id)!;
          return (
            <group key={n.id} position={pos}>
              <Node node={n} isActive={n.id === activeKey} />
            </group>
          );
        })}

        <OrbitControls enablePan enableZoom enableRotate autoRotate autoRotateSpeed={0.4} />
      </Canvas>
    </div>
  );
}
