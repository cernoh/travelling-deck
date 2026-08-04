import { FC } from "react";
import { HorizonState } from "../api";
import { dotPositions, surfacePoint } from "../horizon";

const DOT_COUNT = 11;

// Transparent, pointer-transparent artificial-horizon surface (ADR 0004/0005):
// a horizon line, evenly spaced dots across it, and a transparent lower field
// suggesting the space below the horizon (CONTEXT.md).
//
// PROTOTYPE — not a proven overlay. Decky has not been shown able to keep a
// layer above every game surface, and pointer-events:none does not guarantee
// input pass-through to the game (IMPLEMENTATION.md overlay gate). This
// component only renders the backend's normalized horizon state; a future
// fullscreen mount must pass the on-device compatibility spike first. The
// panel shows it as an in-panel preview.
//
// Renders in CSS-percentage space so it scales with any surface size; the
// surface itself is always transparent and never captures input.
export const HorizonSurface: FC<{ horizon: HorizonState | null }> = ({ horizon }) => {
  const pt = surfacePoint(horizon?.roll ?? 0, horizon?.pitch ?? 0);
  const dots = dotPositions(DOT_COUNT);

  return (
    <div
      aria-hidden="true"
      style={{
        position: "relative",
        width: "100%",
        aspectRatio: "16 / 9",
        overflow: "hidden",
        background: "transparent",
        pointerEvents: "none",
        userSelect: "none",
        touchAction: "none",
      }}
    >
      {/* lower field: translucent wash below the horizon line */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${pt.topPct}%`,
          bottom: 0,
          background: "rgba(255, 255, 255, 0.08)",
          borderTop: "2px solid rgba(255, 255, 255, 0.85)",
        }}
      />
      {/* horizon line with evenly spaced dots */}
      <div
        style={{
          position: "absolute",
          left: `${pt.leftPct}%`,
          top: `${pt.topPct}%`,
          width: "120%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          transform: `translate(-50%, -50%) rotate(${pt.rollDeg}deg)`,
        }}
      >
        {dots.map((x) => (
          <div
            key={x}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "rgba(255, 255, 255, 0.85)",
              flexShrink: 0,
            }}
          />
        ))}
      </div>
      {/* center reference */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          width: 4,
          height: 4,
          borderRadius: "50%",
          background: "rgba(255, 255, 255, 0.5)",
          transform: "translate(-50%, -50%)",
        }}
      />
    </div>
  );
};
