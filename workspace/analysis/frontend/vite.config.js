import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const gatewayPort = Number(process.env.EMPEVER_GATEWAY_PORT || 0);
const base = process.env.VITE_BASE_PATH || (gatewayPort ? "/apps/coding/" : "./");

export default defineConfig({
  plugins: [react()],
  base,
  server: {
    port: 5176,
    strictPort: true,
    host: "127.0.0.1",
    allowedHosts: true,
    ...(gatewayPort
      ? {
          origin: `http://127.0.0.1:${gatewayPort}`,
          // HMR over the :4040 gateway websocket tunnel full-reloads the iframe.
          hmr: false,
        }
      : {}),
  },
});
