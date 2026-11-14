import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import App from "./App";
import "./index.css";

// 深色模式跟著系統設定（docs/ui-review-2.md A5）：index.css 已經有 .dark 的配色，這裡負責加上或拿掉 .dark。
// index.html 也有一段一樣的程式，在 React 載入前先套用，避免先閃一下白底
const dark = window.matchMedia("(prefers-color-scheme: dark)");
const applyTheme = () => document.documentElement.classList.toggle("dark", dark.matches);
applyTheme();
dark.addEventListener("change", applyTheme);

// TanStack Query 的快取：所有頁面共用（ADR-071）
const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
