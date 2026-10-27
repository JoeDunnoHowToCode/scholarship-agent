import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

// 同一個網址呼叫 API：開發時由 Vite 轉發到 FastAPI，做好後由 FastAPI 一起提供（ADR-072）
export const api = createClient<paths>({ baseUrl: "" });

// 後端的 Pydantic 模型產生的型別（ADR-067），例如 Schemas["ScholarshipRow"]
export type Schemas = components["schemas"];

// openapi-fetch 不會丟出錯誤，而是回傳 { data, error }；TanStack Query 要靠丟出錯誤才知道失敗
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  throw new Error(errorMessage(result.error, result.response.status));
}

function errorMessage(error: unknown, status: number): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  // FastAPI 的格式錯誤（422）：detail 是一串錯誤，每一個都有 msg
  if (Array.isArray(detail)) return detail.map((item: { msg?: string }) => item.msg ?? "").join("；");
  return `API 錯誤（${status}）`;
}
