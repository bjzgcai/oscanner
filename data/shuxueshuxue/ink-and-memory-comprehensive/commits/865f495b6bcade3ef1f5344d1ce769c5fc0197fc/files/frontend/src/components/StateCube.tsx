import React, { useState, useRef, useEffect } from 'react';

interface State {
  id: string;
  cn: string;
  en: string;
  locked: boolean;
}

interface CubeFace {
  name: string;
  states: State[];
  unlocked: boolean;
  color: string;
}

// @@@ Quaternion class for smooth 3D rotation
class Quaternion {
  constructor(
    public w: number,
    public x: number,
    public y: number,
    public z: number
  ) {}

  static identity(): Quaternion {
    return new Quaternion(1, 0, 0, 0);
  }

  static fromAxisAngle(axis: { x: number; y: number; z: number }, angle: number): Quaternion {
    const halfAngle = angle / 2;
    const s = Math.sin(halfAngle);
    return new Quaternion(
      Math.cos(halfAngle),
      axis.x * s,
      axis.y * s,
      axis.z * s
    );
  }

  multiply(q: Quaternion): Quaternion {
    return new Quaternion(
      this.w * q.w - this.x * q.x - this.y * q.y - this.z * q.z,
      this.w * q.x + this.x * q.w + this.y * q.z - this.z * q.y,
      this.w * q.y - this.x * q.z + this.y * q.w + this.z * q.x,
      this.w * q.z + this.x * q.y - this.y * q.x + this.z * q.w
    );
  }

  normalize(): Quaternion {
    const mag = Math.sqrt(this.w * this.w + this.x * this.x + this.y * this.y + this.z * this.z);
    return new Quaternion(this.w / mag, this.x / mag, this.y / mag, this.z / mag);
  }

  // @@@ Spherical linear interpolation for smooth animation
  slerp(target: Quaternion, t: number): Quaternion {
    let { w, x, y, z } = this;
    let { w: tw, x: tx, y: ty, z: tz } = target;

    // Compute dot product
    let dot = w * tw + x * tx + y * ty + z * tz;

    // If dot is negative, negate one quaternion to take shorter path
    if (dot < 0) {
      w = -w; x = -x; y = -y; z = -z;
      dot = -dot;
    }

    // If quaternions are very close, use linear interpolation
    if (dot > 0.9995) {
      const result = new Quaternion(
        w + t * (tw - w),
        x + t * (tx - x),
        y + t * (ty - y),
        z + t * (tz - z)
      );
      return result.normalize();
    }

    // Use slerp
    const theta = Math.acos(dot);
    const sinTheta = Math.sin(theta);
    const a = Math.sin((1 - t) * theta) / sinTheta;
    const b = Math.sin(t * theta) / sinTheta;

    return new Quaternion(
      w * a + tw * b,
      x * a + tx * b,
      y * a + ty * b,
      z * a + tz * b
    );
  }

  toRotationMatrix(): string {
    const { w, x, y, z } = this;

    const m00 = 1 - 2 * (y * y + z * z);
    const m01 = 2 * (x * y - w * z);
    const m02 = 2 * (x * z + w * y);

    const m10 = 2 * (x * y + w * z);
    const m11 = 1 - 2 * (x * x + z * z);
    const m12 = 2 * (y * z - w * x);

    const m20 = 2 * (x * z - w * y);
    const m21 = 2 * (y * z + w * x);
    const m22 = 1 - 2 * (x * x + y * y);

    return `matrix3d(${m00},${m10},${m20},0,${m01},${m11},${m21},0,${m02},${m12},${m22},0,0,0,0,1)`;
  }

  // @@@ Transform a vector by this quaternion's rotation
  transformVector(v: { x: number; y: number; z: number }): { x: number; y: number; z: number } {
    const { w, x, y, z } = this;
    const { x: vx, y: vy, z: vz } = v;

    // q * v * q^-1
    const ix = w * vx + y * vz - z * vy;
    const iy = w * vy + z * vx - x * vz;
    const iz = w * vz + x * vy - y * vx;
    const iw = -x * vx - y * vy - z * vz;

    return {
      x: ix * w + iw * -x + iy * -z - iz * -y,
      y: iy * w + iw * -y + iz * -x - ix * -z,
      z: iz * w + iw * -z + ix * -y - iy * -x
    };
  }
}

// @@@ Canonical orientations for each face (facing camera)
const FACE_ORIENTATIONS: Record<string, Quaternion> = {
  front: Quaternion.identity(),
  back: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, Math.PI),
  left: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, Math.PI / 2),
  right: Quaternion.fromAxisAngle({ x: 0, y: 1, z: 0 }, -Math.PI / 2),
  top: Quaternion.fromAxisAngle({ x: 1, y: 0, z: 0 }, Math.PI / 2),  // Swapped
  bottom: Quaternion.fromAxisAngle({ x: 1, y: 0, z: 0 }, -Math.PI / 2)  // Swapped
};

export function StateCube() {
  const [rotation, setRotation] = useState(() => FACE_ORIENTATIONS.front);
  const [isDragging, setIsDragging] = useState(false);
  const [isSnapping, setIsSnapping] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, rotation: Quaternion.identity() });
  const snapAnimationRef = useRef<number | null>(null);

  // @@@ Define 6 faces with 9 states each
  const faces: CubeFace[] = [
    {
      name: 'front',
      unlocked: true,
      color: '#a3d5ff',
      states: [
        { id: 'calm', cn: '平静', en: 'Calm', locked: false },
        { id: 'focused', cn: '专注', en: 'Focused', locked: false },
        { id: 'joyful', cn: '愉悦', en: 'Joyful', locked: false },
        { id: 'confused', cn: '困惑', en: 'Confused', locked: false },
        { id: 'tired', cn: '疲惫', en: 'Tired', locked: false },
        { id: 'curious', cn: '好奇', en: 'Curious', locked: false },
        { id: 'anxious', cn: '焦虑', en: 'Anxious', locked: false },
        { id: 'angry', cn: '愤怒', en: 'Angry', locked: false },
        { id: 'sad', cn: '悲伤', en: 'Sad', locked: false },
      ]
    },
    {
      name: 'back',
      unlocked: false,
      color: '#ffb3d9',
      states: Array(9).fill(null).map((_, i) => ({
        id: `back-${i}`,
        cn: '🔒',
        en: 'Locked',
        locked: true
      }))
    },
    {
      name: 'left',
      unlocked: false,
      color: '#b3ffb3',
      states: Array(9).fill(null).map((_, i) => ({
        id: `left-${i}`,
        cn: '🔒',
        en: 'Locked',
        locked: true
      }))
    },
    {
      name: 'right',
      unlocked: false,
      color: '#ffff43',
      states: Array(9).fill(null).map((_, i) => ({
        id: `right-${i}`,
        cn: '🔒',
        en: 'Locked',
        locked: true
      }))
    },
    {
      name: 'top',
      unlocked: false,
      color: '#ddb3ff',
      states: Array(9).fill(null).map((_, i) => ({
        id: `top-${i}`,
        cn: '🔒',
        en: 'Locked',
        locked: true
      }))
    },
    {
      name: 'bottom',
      unlocked: false,
      color: '#ffd4a3',
      states: Array(9).fill(null).map((_, i) => ({
        id: `bottom-${i}`,
        cn: '🔒',
        en: 'Locked',
        locked: true
      }))
    }
  ];

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      rotation: rotation
    };
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;

    const deltaX = e.clientX - dragStartRef.current.x;
    const deltaY = e.clientY - dragStartRef.current.y;

    // @@@ Convert screen-space drag to rotation axis and angle
    const sensitivity = 0.005;
    const angle = Math.sqrt(deltaX * deltaX + deltaY * deltaY) * sensitivity;

    if (angle > 0.0001) {
      // Rotation axis perpendicular to drag direction (in screen space)
      // deltaY → rotation around X axis, deltaX → rotation around Y axis
      const axis = {
        x: -deltaY,
        y: deltaX,
        z: 0
      };

      // Normalize axis
      const axisMag = Math.sqrt(axis.x * axis.x + axis.y * axis.y);
      if (axisMag > 0) {
        axis.x /= axisMag;
        axis.y /= axisMag;
      }

      // Create delta quaternion and multiply with start rotation
      const deltaQuat = Quaternion.fromAxisAngle(axis, angle);
      const newRotation = deltaQuat.multiply(dragStartRef.current.rotation).normalize();
      setRotation(newRotation);
    }
  };

  // @@@ Find the nearest canonical face orientation
  const findNearestFace = (currentRotation: Quaternion): { name: string; orientation: Quaternion } => {
    let maxDot = -Infinity;
    let nearestFace = 'front';
    let nearestOrientation = FACE_ORIENTATIONS.front;

    // Camera direction (looking at cube from user's perspective)
    const cameraDir = { x: 0, y: 0, z: 1 };

    // Face normals in their local space (each face points toward +Z in its local coords)
    const faceNormals: Record<string, { x: number; y: number; z: number }> = {
      front: { x: 0, y: 0, z: 1 },
      back: { x: 0, y: 0, z: -1 },
      left: { x: -1, y: 0, z: 0 },
      right: { x: 1, y: 0, z: 0 },
      top: { x: 0, y: 1, z: 0 },
      bottom: { x: 0, y: -1, z: 0 }
    };

    for (const [faceName, faceOrientation] of Object.entries(FACE_ORIENTATIONS)) {
      // Get which direction this face is pointing in current rotation
      const localNormal = faceNormals[faceName];
      const worldNormal = currentRotation.transformVector(localNormal);

      // Dot product: how much does this face point toward camera?
      const dot = worldNormal.x * cameraDir.x +
                  worldNormal.y * cameraDir.y +
                  worldNormal.z * cameraDir.z;

      if (dot > maxDot) {
        maxDot = dot;
        nearestFace = faceName;
        nearestOrientation = faceOrientation;
      }
    }

    return { name: nearestFace, orientation: nearestOrientation };
  };

  // @@@ Animate snap to target orientation
  const snapToFace = (targetOrientation: Quaternion) => {
    if (snapAnimationRef.current !== null) {
      cancelAnimationFrame(snapAnimationRef.current);
    }

    const startRotation = rotation;
    const startTime = performance.now();
    const duration = 500; // ms

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const t = Math.min(elapsed / duration, 1);

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);

      const interpolated = startRotation.slerp(targetOrientation, eased);
      setRotation(interpolated);

      if (t < 1) {
        snapAnimationRef.current = requestAnimationFrame(animate);
      } else {
        setIsSnapping(false);
        snapAnimationRef.current = null;
      }
    };

    setIsSnapping(true);
    snapAnimationRef.current = requestAnimationFrame(animate);
  };

  const handleMouseUp = () => {
    setIsDragging(false);

    // @@@ Snap to nearest face
    const { orientation } = findNearestFace(rotation);
    snapToFace(orientation);
  };

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, rotation]);

  // @@@ Cleanup animation on unmount
  useEffect(() => {
    return () => {
      if (snapAnimationRef.current !== null) {
        cancelAnimationFrame(snapAnimationRef.current);
      }
    };
  }, []);

  const renderFace = (face: CubeFace, transform: string) => {
    return (
      <div
        style={{
          position: 'absolute',
          width: '300px',
          height: '300px',
          transform,
          backfaceVisibility: 'hidden',
          background: face.unlocked
            ? `linear-gradient(135deg, ${face.color}40, ${face.color}80)`
            : 'linear-gradient(135deg, #ccc, #999)',
          border: '2px solid rgba(0,0,0,0.1)',
          borderRadius: '8px',
          padding: '10px',
          boxSizing: 'border-box',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gridTemplateRows: 'repeat(3, 1fr)',
          gap: '8px'
        }}
      >
        {face.states.map((state, idx) => (
          <div
            key={state.id}
            style={{
              background: state.locked
                ? 'rgba(255,255,255,0.3)'
                : 'rgba(255,255,255,0.6)',
              borderRadius: '4px',
              padding: '8px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontFamily: "'Excalifont', 'Xiaolai', sans-serif",
              cursor: state.locked ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              opacity: state.locked ? 0.5 : 1,
              userSelect: 'none'
            }}
            onMouseEnter={(e) => {
              if (!state.locked) {
                e.currentTarget.style.transform = 'scale(1.05)';
                e.currentTarget.style.background = 'rgba(255,255,255,0.9)';
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'scale(1)';
              e.currentTarget.style.background = state.locked
                ? 'rgba(255,255,255,0.3)'
                : 'rgba(255,255,255,0.6)';
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: '2px' }}>
              {state.cn}
            </div>
            <div style={{ fontSize: '10px', opacity: 0.7 }}>
              {state.en}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        perspective: '1200px',
        cursor: isDragging ? 'grabbing' : 'grab',
        userSelect: 'none',
        zIndex: 1000
      }}
      onMouseDown={handleMouseDown}
    >
      <div
        style={{
          width: '300px',
          height: '300px',
          position: 'relative',
          transformStyle: 'preserve-3d',
          transform: rotation.toRotationMatrix(),
          transition: (isDragging || isSnapping) ? 'none' : 'transform 0.3s ease-out'
        }}
      >
        {/* Front face */}
        {renderFace(faces[0], 'translateZ(150px)')}

        {/* Back face */}
        {renderFace(faces[1], 'translateZ(-150px) rotateY(180deg)')}

        {/* Left face */}
        {renderFace(faces[2], 'rotateY(-90deg) translateZ(150px)')}

        {/* Right face */}
        {renderFace(faces[3], 'rotateY(90deg) translateZ(150px)')}

        {/* Top face */}
        {renderFace(faces[4], 'rotateX(90deg) translateZ(150px)')}

        {/* Bottom face */}
        {renderFace(faces[5], 'rotateX(-90deg) translateZ(150px)')}
      </div>

      {/* Instruction text */}
      <div style={{
        marginTop: '20px',
        textAlign: 'center',
        color: '#666',
        fontSize: '14px',
        fontFamily: "'Excalifont', 'Xiaolai', sans-serif"
      }}>
        拖拽旋转查看 6 个面 · Drag to rotate
      </div>
    </div>
  );
}
