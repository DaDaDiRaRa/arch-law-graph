import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// data/graph.json 을 web 밖에서 직접 import 하므로 상위 디렉터리 접근 허용
export default defineConfig({
  plugins: [react()],
  // data.js 의 top-level await(graph.json 런타임 fetch) 지원
  build: { target: "es2022" },
  server: {
    fs: { allow: [".."] },
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
