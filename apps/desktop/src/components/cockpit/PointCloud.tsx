import { useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

import type { PointCloudGeometry } from "../../lib/pointCloud";
import { heatPalette } from "./scenePalette";

export interface PointCloudProps {
  cloud: PointCloudGeometry;
  onHoverPoint: (index: number | null) => void;
  onPickPoint: (index: number) => void;
}

/**
 * Nuage Monte Carlo : un seul objet `Points` (pas un mesh par run).
 * `index` renvoyé par R3F est la position dans `cloud.points`.
 */
export function PointCloud({ cloud, onHoverPoint, onPickPoint }: PointCloudProps) {
  const { invalidate } = useThree();

  const geometry = useMemo(() => {
    const next = new THREE.BufferGeometry();
    next.setAttribute("position", new THREE.BufferAttribute(cloud.positions, 3));
    const palette = heatPalette();
    const colors = new Float32Array(cloud.heatSteps.length * 3);
    cloud.heatSteps.forEach((step, index) => {
      const color = palette[step] ?? palette[0];
      colors[index * 3] = color.r;
      colors[index * 3 + 1] = color.g;
      colors[index * 3 + 2] = color.b;
    });
    next.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return next;
  }, [cloud]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <points
      geometry={geometry}
      onPointerMove={(event) => {
        if (event.index === undefined) return;
        onHoverPoint(event.index);
        invalidate();
      }}
      onPointerOut={() => onHoverPoint(null)}
      onClick={(event) => {
        event.stopPropagation();
        if (event.index === undefined) return;
        onPickPoint(event.index);
        invalidate();
      }}
    >
      <pointsMaterial
        vertexColors
        size={0.045}
        sizeAttenuation
        transparent
        opacity={0.9}
        depthWrite={false}
      />
    </points>
  );
}
