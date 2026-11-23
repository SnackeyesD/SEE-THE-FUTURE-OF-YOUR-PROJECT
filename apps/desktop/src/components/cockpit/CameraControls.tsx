import { useThree } from "@react-three/fiber";
import { useCallback, useEffect, useRef } from "react";
import * as THREE from "three";

export interface CameraControlsProps {
  /** Incrémenter pour revenir à la caméra par défaut. */
  resetToken: number;
  /** Vue du dessus, sans réinitialiser les autres réglages. */
  topDown: boolean;
}

const DEFAULT_RADIUS = 3.4;
const DEFAULT_PHI = Math.PI / 3.4;
const DEFAULT_THETA = Math.PI / 4;
const MIN_RADIUS = 1.6;
const MAX_RADIUS = 8;
const MIN_PHI = 0.08;
const MAX_PHI = Math.PI / 2 - 0.02;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

/**
 * Contrôles caméra minimaux (orbite + zoom + reset + vue du dessus) sans
 * dépendance à drei : le chunk 3D reste sous le budget de la phase 14.
 */
export function CameraControls({ resetToken, topDown }: CameraControlsProps) {
  const { camera, gl, invalidate } = useThree();
  const view = useRef({
    point: new THREE.Spherical(DEFAULT_RADIUS, DEFAULT_PHI, DEFAULT_THETA),
    target: new THREE.Vector3(0, 0.35, 0),
  });

  const apply = useCallback(() => {
    const { point, target } = view.current;
    const position = new THREE.Vector3().setFromSpherical(point).add(target);
    camera.position.copy(position);
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    invalidate();
  }, [camera, invalidate]);

  useEffect(() => {
    const { point } = view.current;
    if (topDown) {
      point.phi = MIN_PHI;
      point.theta = 0;
    } else {
      point.radius = DEFAULT_RADIUS;
      point.phi = DEFAULT_PHI;
      point.theta = DEFAULT_THETA;
    }
    apply();
  }, [apply, resetToken, topDown]);

  useEffect(() => {
    const element = gl.domElement;
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      element.setPointerCapture?.(event.pointerId);
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragging) return;
      const deltaX = event.clientX - lastX;
      const deltaY = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      const { point } = view.current;
      point.theta -= deltaX * 0.006;
      point.phi = clamp(point.phi - deltaY * 0.006, MIN_PHI, MAX_PHI);
      apply();
    };
    const onPointerUp = (event: PointerEvent) => {
      dragging = false;
      element.releasePointerCapture?.(event.pointerId);
    };
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const { point } = view.current;
      point.radius = clamp(
        point.radius * Math.exp(event.deltaY * 0.0012),
        MIN_RADIUS,
        MAX_RADIUS,
      );
      apply();
    };

    element.style.touchAction = "none";
    element.addEventListener("pointerdown", onPointerDown);
    element.addEventListener("pointermove", onPointerMove);
    element.addEventListener("pointerup", onPointerUp);
    element.addEventListener("pointercancel", onPointerUp);
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      element.style.touchAction = "";
      element.removeEventListener("pointerdown", onPointerDown);
      element.removeEventListener("pointermove", onPointerMove);
      element.removeEventListener("pointerup", onPointerUp);
      element.removeEventListener("pointercancel", onPointerUp);
      element.removeEventListener("wheel", onWheel);
    };
  }, [apply, gl]);

  return null;
}
