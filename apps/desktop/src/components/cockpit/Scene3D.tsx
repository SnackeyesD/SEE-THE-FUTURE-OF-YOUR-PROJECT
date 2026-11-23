import { Canvas, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

import type { PointCloudGeometry } from "../../lib/pointCloud";
import {
  type SurfaceGeometry,
  type SurfaceMarker,
} from "../../lib/surface3d";
import { measureFrameRate, observeContextLoss } from "../../lib/webgl";
import { CameraControls } from "./CameraControls";
import { PointCloud } from "./PointCloud";
import { accentColor } from "./scenePalette";
import { SurfaceMesh } from "./SurfaceMesh";

export interface Scene3DProps {
  geometry: SurfaceGeometry;
  xValues: number[];
  yValues: number[];
  marker: SurfaceMarker | null;
  cloud: PointCloudGeometry | null;
  mode: "surface" | "cloud";
  resetToken: number;
  topDown: boolean;
  onPickCell: (column: number, row: number) => void;
  onHoverCell: (cell: { column: number; row: number } | null) => void;
  onPickPoint: (index: number) => void;
  onHoverPoint: (index: number | null) => void;
  onContextLost: () => void;
  onFrameRate: (fps: number) => void;
}

function SceneBridge({
  onContextLost,
  onFrameRate,
}: Pick<Scene3DProps, "onContextLost" | "onFrameRate">) {
  const { gl } = useThree();

  useEffect(
    () =>
      observeContextLoss(gl.domElement as unknown as {
        addEventListener?: (type: string, listener: () => void) => void;
        removeEventListener?: (type: string, listener: () => void) => void;
      }, onContextLost),
    [gl, onContextLost],
  );

  useEffect(() => {
    let cancelled = false;
    void measureFrameRate({ durationMs: 2000 }).then((fps) => {
      if (!cancelled && fps > 0) onFrameRate(fps);
    });
    return () => {
      cancelled = true;
    };
  }, [onFrameRate]);

  return null;
}

function Marker({ marker }: { marker: SurfaceMarker }) {
  const markerLine = useMemo(() => {
    const color = accentColor();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(
        [
          marker.position[0],
          0,
          marker.position[2],
          marker.position[0],
          marker.position[1],
          marker.position[2],
        ],
        3,
      ),
    );
    const material = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.7,
    });
    return { object: new THREE.Line(geometry, material), geometry, material, color };
  }, [marker]);

  useEffect(
    () => () => {
      markerLine.geometry.dispose();
      markerLine.material.dispose();
    },
    [markerLine],
  );

  return (
    <group>
      <mesh position={marker.position}>
        <sphereGeometry args={[0.04, 16, 12]} />
        <meshBasicMaterial color={markerLine.color} />
      </mesh>
      <primitive object={markerLine.object} />
    </group>
  );
}

/**
 * Scène Three.js chargée dynamiquement. Elle ne reçoit que des données déjà
 * agrégées (`geometry`, `cloud`) : aucun calcul métier, aucun accès au store.
 */
export default function Scene3D({
  geometry,
  xValues,
  yValues,
  marker,
  cloud,
  mode,
  resetToken,
  topDown,
  onPickCell,
  onHoverCell,
  onPickPoint,
  onHoverPoint,
  onContextLost,
  onFrameRate,
}: Scene3DProps) {
  return (
    <Canvas
      className="scene3d__canvas"
      dpr={[1, 2]}
      frameloop="demand"
      camera={{ position: [2.4, 2.2, 2.8], fov: 42, near: 0.01, far: 50 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      aria-label="Vue 3D de la surface"
    >
      <SceneBridge onContextLost={onContextLost} onFrameRate={onFrameRate} />
      <ambientLight intensity={0.9} />
      <directionalLight position={[3, 5, 2]} intensity={1.3} />
      <directionalLight position={[-3, 2, -2]} intensity={0.4} />
      {mode === "surface" ? (
        <>
          <SurfaceMesh
            geometry={geometry}
            xValues={xValues}
            yValues={yValues}
            onPickCell={onPickCell}
            onHoverCell={onHoverCell}
          />
          {marker ? <Marker marker={marker} /> : null}
        </>
      ) : null}
      {mode === "cloud" && cloud ? (
        <PointCloud
          cloud={cloud}
          onHoverPoint={onHoverPoint}
          onPickPoint={onPickPoint}
        />
      ) : null}
      <CameraControls resetToken={resetToken} topDown={topDown} />
    </Canvas>
  );
}
