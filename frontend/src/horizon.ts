// Pure geometry for the artificial-horizon prototype surface.
//
// Inputs are the backend's normalized horizon state (range [-1, 1]); outputs
// are CSS-percentage positions so the surface never needs pixel math at
// render time and resizes cleanly with any display surface (ADR 0004
// normalization). No DOM, no React — kept erasable-TypeScript so node can run
// it directly (see horizon.test.ts).

export const MAX_ROLL_DEG = 30; // full deflection at roll = ±1
export const MAX_PITCH_PCT = 35; // horizon-line travel (in % of height) at pitch = ±1

export interface SurfacePoint {
  leftPct: number; // 0..100, horizontal center of the horizon line
  topPct: number; // 0..100, vertical center of the horizon line
  rollDeg: number; // line rotation, bounded to ±MAX_ROLL_DEG
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

export function rollDegrees(roll: number): number {
  return clamp(roll, -1, 1) * MAX_ROLL_DEG;
}

export function pitchOffsetPct(pitch: number): number {
  // pitch +1 (nose up) moves the horizon line down the screen, matching a
  // pilot's view of the real horizon.
  return clamp(pitch, -1, 1) * MAX_PITCH_PCT;
}

export function surfacePoint(roll: number, pitch: number): SurfacePoint {
  return {
    leftPct: 50,
    topPct: 50 + pitchOffsetPct(pitch),
    rollDeg: rollDegrees(roll),
  };
}

// Evenly spaced dots across the horizon line, normalized -1..1 (left..right).
export function dotPositions(count: number): number[] {
  if (count < 1) return [];
  if (count === 1) return [0];
  return Array.from({ length: count }, (_, i) => (i / (count - 1)) * 2 - 1);
}
