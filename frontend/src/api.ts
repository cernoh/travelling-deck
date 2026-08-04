// Virtual Horizon — Decky bridge contract.
//
// The Python backend must implement exactly these plugin method names and
// payload shapes. Decky's bridge resolves each route string to a method of
// the same name on the backend Plugin class.
//
// Contract (snake_case routes match the Python backend):
//   get_state()                                                  -> PluginState
//   set_enabled({ enabled: boolean })                            -> PluginState
//   acknowledge_notice()                                         -> PluginState
//   set_report_consent({ consent: boolean })                     -> PluginState
//   submit_comfort_report({ rating_before: 1..5, rating_after: 1..5,
//                           comment?: string })                  -> { submitted: boolean, error?: string }
//   get_diagnostics()                                            -> Diagnostics
//
// The backend is authoritative for everything: sensor capability (fail closed
// without both accelerometer and gyroscope, ADR 0012), activation state
// (manual toggle, default off, ADR 0007), the safety latch (erratic motion or
// sensor loss, ADR 0011), and horizon render state (ADR 0003/0008). The
// frontend only renders what the backend reports and never activates itself.

import { callable } from "@decky/api";

// --- shared types ---------------------------------------------------------

// Backend state machine (IMPLEMENTATION.md): Unavailable -> Ready -> Active
// <-> Degraded -> Active; SafetyDisabled is latched from Active/Degraded.
export type PluginStatus =
  | "unavailable" // required sensors missing or unreadable
  | "ready" // sensors OK, user has not enabled
  | "active" // enabled and tracking
  | "degraded" // enabled, bounded prediction while confidence is low
  | "safety_disabled"; // latched off by erratic-motion or sensor failure

export interface SensorState {
  present: boolean; // device detected on this machine
  readable: boolean; // open and sampling without errors
}

export interface Sensors {
  accelerometer: SensorState;
  gyroscope: SensorState;
}

export interface HorizonState {
  // Normalized device-relative horizon, each in [-1, 1]:
  roll: number; // +1 = right side down
  pitch: number; // +1 = nose up
  confidence: number; // 0..1
  degraded: boolean; // backend is in bounded-prediction mode
  timestamp: number; // epoch ms of the sample
}

export interface PluginState {
  enabled: boolean; // manual toggle; defaults to off (ADR 0007)
  status: PluginStatus;
  sensors: Sensors;
  safety_latch: boolean; // stays latched until user re-enables
  disable_reason: "manual" | "erratic_motion" | "sensor_loss" | null;
  notice_acknowledged: boolean; // one-time kinetosis notice (ADR 0010)
  report_consent: boolean; // opt-in anonymous comfort reports (ADR 0013)
  horizon: HorizonState | null; // null while inactive/unavailable
}

export interface Diagnostics {
  sensors: {
    accelerometer: SensorState & { samples: number; last_error: string | null };
    gyroscope: SensorState & { samples: number; last_error: string | null };
  };
  horizon: {
    confidence: number;
    degraded: boolean;
    safety_disables: number; // lifetime count
    last_disable_reason: string | null;
  };
}

export interface ComfortReport {
  rating_before: number; // 1..5
  rating_after: number; // 1..5
  comment?: string; // optional free-form text
}

// --- bridge methods -------------------------------------------------------

export const getState = callable<[], PluginState>("get_state");
export const setEnabled = callable<[{ enabled: boolean }], PluginState>("set_enabled");
export const acknowledgeNotice = callable<[], PluginState>("acknowledge_notice");
export const setReportConsent = callable<[{ consent: boolean }], PluginState>("set_report_consent");
export const submitComfortReport = callable<
  [ComfortReport],
  { submitted: boolean; error?: string }
>("submit_comfort_report");
export const getDiagnostics = callable<[], Diagnostics>("get_diagnostics");
