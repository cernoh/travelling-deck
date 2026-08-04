import deckyPlugin from "@decky/rollup";

// Decky rollup preset. Run from frontend/ (npm run build).
// Input is fixed to ./src/index.tsx; the plugin manifest (plugin.json) is
// read from the repo root via sourceRoot "..".
export default deckyPlugin({}, "..");
