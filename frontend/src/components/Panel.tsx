import { FC, useEffect, useState } from "react";
import {
  ButtonItem,
  DialogButton,
  Focusable,
  PanelSection,
  PanelSectionRow,
  SliderField,
  TextField,
  ToggleField,
} from "@decky/ui";
import {
  acknowledgeNotice,
  Diagnostics,
  getDiagnostics,
  PluginState,
  setEnabled,
  setReportConsent,
  submitComfortReport,
} from "../api";
import { usePluginState } from "../hooks";
import { HorizonSurface } from "./HorizonSurface";

// Panel sections, top to bottom:
//  1. one-time kinetosis notice (ADR 0010) until acknowledged
//  2. enable/disable + status (ADR 0007, 0011, 0012)
//  3. horizon prototype preview (ADR 0004/0005, prototype only)
//  4. opt-in comfort reports (ADR 0013)
//  5. on-demand diagnostics (ADR 0002, 0010, 0011)
export const Panel: FC = () => {
  const state = usePluginState();

  return (
    <Focusable style={{ flexDirection: "column", gap: "8px" }}>
      {state && !state.notice_acknowledged && (
        <PanelSection title="Notice">
          <PanelSectionRow>
            <HealthNotice onAcknowledge={() => void acknowledgeNotice()} />
          </PanelSectionRow>
        </PanelSection>
      )}
      <PanelSection title="Virtual Horizon">
        <PanelSectionRow>
          <ToggleField
            label="Show virtual horizon"
            description={
              state === null
                ? "Connecting to the backend…"
                : sensorProblem(state) ?? statusDescription(state)
            }
            checked={state?.enabled ?? false}
            disabled={state === null || sensorProblem(state) !== null}
            onChange={(enabled) => void setEnabled({ enabled })}
          />
        </PanelSectionRow>
      </PanelSection>
      <PanelSection title="Horizon surface (prototype)">
        <PanelSectionRow>
          <HorizonPreview state={state} />
        </PanelSectionRow>
      </PanelSection>
      {state && <ComfortSection state={state} />}
      {state && <DiagnosticsSection state={state} />}
    </Focusable>
  );
};

// ---------------------------------------------------------------------------

// ADR 0010: concise one-time notice — aims to reduce kinetosis, does not
// guarantee prevention. Stored acknowledged in backend settings.
const HealthNotice: FC<{ onAcknowledge: () => void }> = ({ onAcknowledge }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
    <p style={{ margin: 0 }}>
      Virtual Horizon aims to reduce kinetosis (motion sickness) during travel
      by showing a stable visual reference. It does not guarantee prevention
      and is not a medical product.
    </p>
    <DialogButton onClick={onAcknowledge}>I understand</DialogButton>
  </div>
);

// ADR 0012: fail closed without both sensors. Returns a reason the panel is
// unsupported, or null when the pair is present and readable.
function sensorProblem(state: PluginState): string | null {
  const missing = [
    !state.sensors.accelerometer.present && "accelerometer",
    !state.sensors.gyroscope.present && "gyroscope",
  ].filter(Boolean) as string[];
  if (missing.length > 0) return `unsupported: ${missing.join(" and ")} unavailable`;

  const unreadable = [
    state.sensors.accelerometer.present && !state.sensors.accelerometer.readable && "accelerometer",
    state.sensors.gyroscope.present && !state.sensors.gyroscope.readable && "gyroscope",
  ].filter(Boolean) as string[];
  if (unreadable.length > 0) return `unsupported: ${unreadable.join(" and ")} present but not readable`;

  return null;
}

function statusDescription(state: PluginState): string {
  switch (state.status) {
    case "ready":
      return "Ready — sensors OK. Enable to show the horizon.";
    case "active":
      return "Active.";
    case "degraded":
      return "Active with degraded sensor confidence — bounded prediction only.";
    case "safety_disabled": {
      const reason =
        state.disable_reason === "erratic_motion"
          ? "erratic motion detected"
          : state.disable_reason === "sensor_loss"
            ? "sensor loss"
            : "disabled manually";
      return `Safety disabled (${reason}). Re-enable to resume after sensors recover.`;
    }
    case "unavailable":
      return "Unavailable — horizon estimation is not running.";
  }
}

// ---------------------------------------------------------------------------
// Horizon prototype preview. Only rendered with real backend horizon data;
// a level placeholder would imply a level estimate that does not exist
// (ADR 0012). The surface is pointer-transparent and normalized.
const HorizonPreview: FC<{ state: PluginState | null }> = ({ state }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
    {state?.horizon ? (
      <>
        <div style={{ border: "1px solid rgba(255, 255, 255, 0.2)", borderRadius: "8px" }}>
          <HorizonSurface horizon={state.horizon} />
        </div>
        <p style={{ margin: 0, fontSize: "12px", opacity: 0.7 }}>
          Prototype surface — transparent and pointer-transparent (no input
          capture). A full-screen overlay above gameplay is not yet proven on
          Decky; this preview renders the backend's normalized horizon state
          only.
        </p>
      </>
    ) : (
      <p style={{ margin: 0, fontSize: "12px", opacity: 0.7 }}>
        No horizon data — the backend is inactive or unavailable. Nothing is
        shown rather than implying a level estimate.
      </p>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// ADR 0013: opt-in anonymous comfort reports. Nothing is collected until the
// user opts in and submits; submission failure is non-blocking.
const ComfortSection: FC<{ state: PluginState }> = ({ state }) => {
  const [before, setBefore] = useState(3);
  const [after, setAfter] = useState(3);
  const [comment, setComment] = useState("");
  const [outcome, setOutcome] = useState<"submitted" | "error" | null>(null);

  const submit = async () => {
    setOutcome(null);
    try {
      const res = await submitComfortReport({
        rating_before: before,
        rating_after: after,
        comment: comment.trim() || undefined,
      });
      setOutcome(res.submitted ? "submitted" : "error");
    } catch {
      setOutcome("error");
    }
  };

  return (
    <PanelSection title="Comfort reports">
      <PanelSectionRow>
        <ToggleField
          label="Share anonymous comfort reports"
          description="Optional before/after comfort ratings to evaluate kinetosis reduction. Nothing is sent until you opt in and submit."
          checked={state.report_consent}
          onChange={(consent) => {
            setOutcome(null);
            void setReportConsent({ consent });
          }}
        />
      </PanelSectionRow>
      {state.report_consent &&
        (outcome === null ? (
          <>
            <PanelSectionRow>
              <SliderField
                label="Comfort before travel"
                value={before}
                min={1}
                max={5}
                step={1}
                notchCount={5}
                showValue
                onChange={setBefore}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Comfort after travel"
                value={after}
                min={1}
                max={5}
                step={1}
                notchCount={5}
                showValue
                onChange={setAfter}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField label="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem onClick={() => void submit()}>Submit report</ButtonItem>
            </PanelSectionRow>
          </>
        ) : outcome === "submitted" ? (
          <PanelSectionRow>
            <p style={{ margin: 0 }}>Report submitted — thank you.</p>
          </PanelSectionRow>
        ) : (
          <PanelSectionRow>
            <p style={{ margin: 0 }}>
              Submission failed — you can try again. Nothing was sent.
            </p>
          </PanelSectionRow>
        ))}
    </PanelSection>
  );
};

// ---------------------------------------------------------------------------
// ADR 0002/0010/0011: diagnostics on demand, never persistently displayed
// over gameplay. Loads while expanded and refreshes every 2s.
const DiagnosticsSection: FC<{ state: PluginState }> = () => {
  const [open, setOpen] = useState(false);
  const [diag, setDiag] = useState<Diagnostics | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const load = async () => {
      try {
        const d = await getDiagnostics();
        if (!cancelled) setDiag(d);
      } catch {
        // keep last known diagnostics
      }
    };
    void load();
    const id = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [open]);

  return (
    <PanelSection title="Diagnostics">
      <PanelSectionRow>
        <ToggleField
          label="Show sensor and horizon diagnostics"
          description="On-demand detail; never shown over gameplay."
          checked={open}
          onChange={setOpen}
        />
      </PanelSectionRow>
      {open &&
        (diag ? (
          <>
            <PanelSectionRow>
              <p style={{ margin: 0 }}>Accelerometer: {sensorSummary(diag.sensors.accelerometer)}</p>
            </PanelSectionRow>
            <PanelSectionRow>
              <p style={{ margin: 0 }}>Gyroscope: {sensorSummary(diag.sensors.gyroscope)}</p>
            </PanelSectionRow>
            <PanelSectionRow>
              <p style={{ margin: 0 }}>
                Horizon confidence: {Math.round(diag.horizon.confidence * 100)}%
                {diag.horizon.degraded ? " (degraded)" : ""}
              </p>
            </PanelSectionRow>
            <PanelSectionRow>
              <p style={{ margin: 0 }}>
                Safety disables: {diag.horizon.safety_disables}
                {diag.horizon.last_disable_reason ? ` — last: ${diag.horizon.last_disable_reason}` : ""}
              </p>
            </PanelSectionRow>
          </>
        ) : (
          <PanelSectionRow>
            <p style={{ margin: 0 }}>Loading diagnostics…</p>
          </PanelSectionRow>
        ))}
    </PanelSection>
  );
};

function sensorSummary(s: { present: boolean; readable: boolean; samples: number; last_error: string | null }): string {
  if (!s.present) return "not present";
  if (!s.readable) return `present, not readable${s.last_error ? ` (${s.last_error})` : ""}`;
  return `ok — ${s.samples} samples${s.last_error ? ` (${s.last_error})` : ""}`;
}
