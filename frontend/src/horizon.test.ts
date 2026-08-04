import { test } from "node:test";
import assert from "node:assert/strict";
import {
  dotPositions,
  MAX_PITCH_PCT,
  MAX_ROLL_DEG,
  pitchOffsetPct,
  rollDegrees,
  surfacePoint,
} from "./horizon.ts";

test("roll is clamped and scaled to MAX_ROLL_DEG", () => {
  assert.equal(rollDegrees(1), MAX_ROLL_DEG);
  assert.equal(rollDegrees(-1), -MAX_ROLL_DEG);
  assert.equal(rollDegrees(0.5), MAX_ROLL_DEG * 0.5);
  assert.equal(rollDegrees(5), MAX_ROLL_DEG); // out-of-range clamps
  assert.equal(rollDegrees(-5), -MAX_ROLL_DEG);
});

test("pitch moves the horizon line opposite to travel", () => {
  assert.equal(pitchOffsetPct(0), 0);
  assert.equal(pitchOffsetPct(1), MAX_PITCH_PCT); // nose up -> line down
  assert.equal(pitchOffsetPct(-1), -MAX_PITCH_PCT);
  assert.equal(pitchOffsetPct(-2), -MAX_PITCH_PCT); // clamps
});

test("surfacePoint keeps the line centered horizontally", () => {
  const p = surfacePoint(0.4, -0.6);
  assert.equal(p.leftPct, 50);
  assert.equal(p.topPct, 50 + pitchOffsetPct(-0.6));
  assert.equal(p.rollDeg, rollDegrees(0.4));
});

test("dots are evenly spaced across -1..1", () => {
  assert.deepEqual(dotPositions(3), [-1, 0, 1]);
  assert.deepEqual(dotPositions(5), [-1, -0.5, 0, 0.5, 1]);
  assert.deepEqual(dotPositions(1), [0]);
  assert.deepEqual(dotPositions(0), []);
});
