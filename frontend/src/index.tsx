import { definePlugin } from "@decky/api";
import { Panel } from "./components/Panel";

export default definePlugin(() => ({
  name: "Virtual Horizon",
  version: "0.1.0",
  icon: (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <line x1="3" y1="12" x2="21" y2="12" />
      <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
    </svg>
  ),
  content: <Panel />,
}));
