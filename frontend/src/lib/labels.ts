// 代號換成中文；後端的代號見 backend/app/features/scholarships/schemas.py 與 matching/score.py

export const DEGREE_NAMES: Record<string, string> = { bachelor: "學士", master: "碩士", phd: "博士" };

// 時間狀態（ADR-059）：還能申請 → 時間待確認 → 已截止或不適用
export const GROUP_NAMES: Record<string, string> = {
  pass: "還能申請",
  unclear: "時間待確認",
  fail: "已截止或不適用",
};

export const CHECK_NAMES: Record<string, string> = { nationality: "國籍", degree: "學位", time: "時間" };
export const RESULT_NAMES: Record<string, string> = { pass: "符合", unclear: "待確認", fail: "不符合" };
export const SUB_SCORE_NAMES: Record<string, string> = { field: "領域契合", country: "想去的國家" };

export const SCOPE_NAMES: Record<string, string> = {
  all: "不限國籍",
  listed: "只限列出的國家",
  excluded: "列出的國家以外都可以",
  unclear: "原文沒寫",
};

export const CYCLE_STATUS_NAMES: Record<string, string> = {
  open: "開放中",
  upcoming: "即將開放",
  closed: "已截止",
  estimated: "預估",
};

// 不是申請獎學金的日期（ADR-105）
export const OTHER_DATE_NAMES: Record<string, string> = {
  admission_only: "只有入學申請",
  document: "補件與文件",
  payment: "繳費",
  other: "其他時程",
};

export const FUNDING_NAMES: Record<string, string> = { scholarship: "申請獎學金", self_funded: "自費", any: "不限" };

// 驗證者的結果（ADR-008、045、053）
export const VERIFICATION_NAMES: Record<string, string> = {
  supported: "已核對",
  catalogue: "依 EACEA 目錄頁",
  empty: "沒抽到",
  no_evidence: "沒附引用",
  quote_not_found: "引用不在原文",
  not_supported: "引用不支持",
  conflict: "各節說法不同",
  year_not_in_quote: "年份不在引用裡",
  degree_not_in_quote: "學位不在引用裡",
  incomplete: "日期不齊全",
  closes_before_opens: "截止早於開放",
};

export const DOC_NAMES: Record<string, string> = {
  cv: "履歷",
  motivation_letter: "動機信",
  recommendation_letter: "推薦信",
  transcript: "成績單",
  degree_certificate: "學位證書",
  language_test: "語言檢定",
  passport: "護照",
  research_proposal: "研究計畫",
  portfolio: "作品集",
  admission_letter: "入學許可",
  financial_proof: "財力證明",
  application_form: "申請表",
  other: "其他",
};

// 金額（ADR-070）
export const AMOUNT_KIND_NAMES: Record<string, string> = {
  living_allowance: "生活津貼",
  tuition_coverage: "學費補助",
  travel: "旅費",
  other: "其他",
};
export const AMOUNT_PERIOD_NAMES: Record<string, string> = {
  month: "每月",
  year: "每年",
  total: "總額",
  once: "一次",
  unclear: "",
};
export const AMOUNT_STATUS_NAMES: Record<string, string> = {
  supported: "已核對",
  no_evidence: "沒附引用",
  invalid_currency: "幣別代碼不對",
  quote_not_found: "引用不在原文",
  number_not_in_quote: "數字不在引用裡",
  period_mismatch: "期間和引用不合",
};

export const EVENT_KIND_NAMES: Record<string, string> = {
  new_scholarship: "新獎學金",
  new_cycle: "新年度公布",
  cycle_opened: "已開放",
  deadline: "截止提醒",
  change: "資料變更",
  system: "系統",
};
export const EVENT_STATUS_NAMES: Record<string, string> = { pending: "待送", sent: "已送", failed: "失敗" };

// 類別的程式檢查發現的問題（ADR-045），例如 degree_not_in_quote:bachelor
const ISSUE_NAMES: Record<string, string> = {
  name_not_in_source: "類別名稱不在原文",
  quota_not_in_source: "名額不在原文",
};

export function issueName(issue: string): string {
  const [code, detail] = issue.split(":");
  if (code === "degree_not_in_quote" && detail) return `${nameOf(DEGREE_NAMES, detail)}不在學位引用裡`;
  return nameOf(ISSUE_NAMES, code);
}

// 代號換成中文；沒有對應的照原樣顯示，空值顯示「—」
export function nameOf(names: Record<string, string>, code: string | null | undefined): string {
  return code ? (names[code] ?? code) : "—";
}

const TAIPEI = new Intl.DateTimeFormat("zh-TW", {
  timeZone: "Asia/Taipei",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

// API 的時間都是 UTC；畫面上換成台灣時間。「台灣時間」寫在頁尾一次，不在每個時間後面重複（docs/ui-review-2.md A4）
export function taipeiTime(iso: string | null | undefined): string {
  return iso ? TAIPEI.format(new Date(iso)) : "—";
}

// 第 10 天段 6：發掘 agent 的任務與結果、來源狀態
export const AGENT_TASK_NAMES: Record<string, string> = {
  universities: "逐校找",
  search: "搜尋補漏",
  new_url: "找新網址",
  smoke: "測試",
};
export const AGENT_RESULT_NAMES: Record<string, string> = {
  done: "完成",
  step_limit: "步數到上限",
  cost_limit: "費用到上限",
  stopped: "停止",
  error: "出錯",
};
// 每月 AI 費用依功能分（llm_calls.feature，紀錄頁）
export const FEATURE_NAMES: Record<string, string> = {
  extract: "抽取",
  outline: "長文件大綱",
  section: "長文件分段抽取",
  verify: "核對",
  table: "表格說明",
  links: "找子頁",
  topics: "段落主題",
  score: "評分",
  route: "問答分類",
  answer: "問答回答",
  dedup: "重複比對",
  summary: "說明",
  "summary-check": "說明核對",
  amounts: "金額補抽",
  transcribe: "PDF 轉錄",
  "agent-university": "逐校找網站",
  "agent-search": "搜尋補漏",
  "agent-new-url": "找新網址",
  "agent-smoke": "測試",
};
export const SOURCE_STATUS_NAMES: Record<string, string> = { candidate: "候選", approved: "已加入", rejected: "已排除" };
