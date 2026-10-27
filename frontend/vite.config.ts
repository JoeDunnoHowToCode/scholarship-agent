import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // @/ 代表 src/（shadcn 的元件用這個寫法 import）
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  // 開發時把 /api 轉發到 FastAPI：瀏覽器看起來是同一個網址，不需要 CORS（ADR-072）
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
