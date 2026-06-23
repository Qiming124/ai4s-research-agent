import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

const API_TARGET = "http://127.0.0.1:8000";

/** 开发代理：对 SSE 关闭缓冲，与生产 Nginx proxy_buffering off 对齐 */
function apiProxy(): ProxyOptions {
  return {
    target: API_TARGET,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on("proxyRes", (proxyRes, _req, res) => {
        const ct = proxyRes.headers["content-type"];
        if (ct && String(ct).includes("text/event-stream")) {
          proxyRes.headers["x-accel-buffering"] = "no";
          proxyRes.headers["cache-control"] = "no-cache";
          res.setHeader("X-Accel-Buffering", "no");
          res.setHeader("Cache-Control", "no-cache");
          res.setHeader("Connection", "keep-alive");
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": apiProxy(),
      "/health": apiProxy(),
    },
  },
  build: {
    outDir: "dist",
  },
});
