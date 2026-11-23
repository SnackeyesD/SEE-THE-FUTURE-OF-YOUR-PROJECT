import { useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

import {
  MISSING_CELL,
  pickSurfaceCell,
  type SurfaceGeometry,
} from "../../lib/surface3d";
import { heatPalette } from "./scenePalette";

export interface SurfaceMeshProps {
  geometry: SurfaceGeometry;
  xValues: number[];
  yValues: number[];
  onPickCell: (column: number, row: number) => void;
  onHoverCell: (cell: { column: number; row: number } | null) => void;
}

/**
 * Mesh de la surface. Les sommets viennent de `buildSurfaceGeometry` ; les
 * couleurs sont les paliers de la heatmap 2D, lues depuis les tokens CSS.
 */
export function SurfaceMesh({
  geometry,
  xValues,
  yValues,
  onPickCell,
  onHoverCell,
}: SurfaceMeshProps) {
  const { invalidate } = useThree();

  const mesh = useMemo(() => {
    const next = new THREE.BufferGeometry();
    next.setAttribute("position", new THREE.BufferAttribute(geometry.positions, 3));
    next.setIndex(new THREE.BufferAttribute(geometry.indices, 1));

    const palette = heatPalette();
    const colors = new Float32Array(geometry.heatSteps.length * 3);
    geometry.heatSteps.forEach((step, index) => {
      const color = step === MISSING_CELL ? palette[0] : (palette[step] ?? palette[0]);
      colors[index * 3] = color.r;
      colors[index * 3 + 1] = color.g;
      colors[index * 3 + 2] = color.b;
    });
    next.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    next.computeVertexNormals();
    return next;
  }, [geometry]);

  useEffect(() => () => mesh.dispose(), [mesh]);

  return (
    <mesh
      geometry={mesh}
      onPointerMove={(event) => {
        const cell = pickSurfaceCell({ x: event.point.x, z: event.point.z }, { xValues, yValues });
        onHoverCell(cell ? { column: cell.column, row: cell.row } : null);
      }}
      onPointerOut={() => onHoverCell(null)}
      onClick={(event) => {
        event.stopPropagation();
        const cell = pickSurfaceCell({ x: event.point.x, z: event.point.z }, { xValues, yValues });
        if (!cell) return;
        onPickCell(cell.column, cell.row);
        invalidate();
      }}
    >
      <meshStandardMaterial
        vertexColors
        side={THREE.DoubleSide}
        roughness={0.72}
        metalness={0.05}
        flatShading={false}
      />
    </mesh>
  );
}
