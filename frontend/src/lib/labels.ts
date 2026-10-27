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

export const EVENT_KIND_NAMES: Record<string, string> = {
  new_scholarship: "新獎學金",
  new_cycle: "新年度開放",
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

// API 的時間都是 UTC；畫面上換成台灣時間
export function taipeiTime(iso: string | null | undefined): string {
  return iso ? `${TAIPEI.format(new Date(iso))}（台灣時間）` : "—";
}
