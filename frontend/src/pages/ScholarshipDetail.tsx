import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsPanel, TabsTab } from "@/components/ui/tabs";
import {
  AMOUNT_KIND_NAMES,
  AMOUNT_PERIOD_NAMES,
  AMOUNT_STATUS_NAMES,
  CHECK_NAMES,
  DEGREE_NAMES,
  DOC_NAMES,
  FUNDING_NAMES,
  RESULT_NAMES,
  SCOPE_NAMES,
  SUB_SCORE_NAMES,
  VERIFICATION_NAMES,
  issueName,
  nameOf,
  taipeiTime,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

type Detail = Schemas["ScholarshipDetail"];
type Score = Schemas["ScoreOut"];
type Check = { result: string; reason: string };
type SubScore = { score: number | null; reason: string };

const TABS = [
  { value: "apply", label: "申請" },
  { value: "eligibility", label: "資格" },
  { value: "score", label: "評分" },
  { value: "history", label: "紀錄" },
];

export default function ScholarshipDetail() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.value === params.get("tab"))?.value ?? "apply";
  const detail = useQuery({
    queryKey: ["scholarship", id],
    queryFn: async () =>
      unwrap(await api.GET("/api/scholarships/{scholarship_id}", { params: { path: { scholarship_id: id } } })),
  });

  if (detail.isPending) return <Skeleton className="h-96 w-full" />;
  if (detail.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到這筆獎學金</AlertTitle>
        <AlertDescription>{detail.error.message}</AlertDescription>
      </Alert>
    );
  const d = detail.data;
  return (
    <div className="space-y-4">
      <BackToList />
      {/* 頁首（ADR-090）：左邊名稱，右邊同一列放「前往官方網站」；窄螢幕時按鈕換到名稱下方 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h1 className="text-xl font-semibold">{d.name}</h1>
          <p className="text-muted-foreground">{[d.name_zh, d.provider].filter(Boolean).join("｜")}</p>
          {(d.stale || d.status === "archived") && (
            <div className="flex flex-wrap gap-2">
              {d.stale && <Badge variant="destructive">資料過舊</Badge>}
              {d.status === "archived" && <Badge variant="secondary">已封存</Badge>}
            </div>
          )}
        </div>
        {d.official_url && (
          <a
            href={d.official_url}
            target="_blank"
            rel="noreferrer"
            className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto")}
          >
            前往官方網站 ↗
          </a>
        )}
      </div>
      <Summary detail={d} />
      {/* 其餘內容分頁籤（ADR-090），選到的頁籤記在網址 ?tab=，重新整理和上一頁都會回到同一個。
          內容只在選到時才畫：Base UI 會等離場動畫跑完才移除舊面板，分頁在背景時動畫不會跑，新舊內容會同時出現 */}
      <Tabs value={tab} onValueChange={(value) => setParams({ tab: String(value) }, { replace: true })}>
        <TabsList>
          {TABS.map((t) => (
            <TabsTab key={t.value} value={t.value}>
              {t.label}
            </TabsTab>
          ))}
        </TabsList>
        <TabsPanel value="apply">
          {tab === "apply" && (
            <>
              <Section title="申請期">
                {/* 11-07：原本是四欄表格，第一欄不換行把其他欄擠成一字一行；改成每一期一塊，由上往下讀 */}
                <ul className="divide-y">
                  {d.cycles.map((c, index) => (
                    <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                      {/* 例如「2026-10-20 → 2027-01-11（開放中）Grant application period」：狀態已經在括號裡 */}
                      <p className="font-medium">{c.description}</p>
                      <p className="text-muted-foreground">
                        {[
                          `截止 ${taipeiTime(c.closes_at)}`,
                          !c.estimated && nameOf(VERIFICATION_NAMES, c.verification),
                          `${nameOf(SCOPE_NAMES, c.nationality_scope)}${c.nationalities.length > 0 ? `（${c.nationalities.length} 國）` : ""}`,
                          nameOf(FUNDING_NAMES, c.funding),
                        ]
                          .filter(Boolean)
                          .join("｜")}
                      </p>
                      {c.evidence && <p className="max-w-prose text-muted-foreground">「{c.evidence}」</p>}
                    </li>
                  ))}
                </ul>
                {d.cycles.length === 0 && <p className="text-sm text-muted-foreground">原文沒有截止日</p>}
              </Section>
              <Section title="補助">
                <Fact label="補助內容">{d.coverage ?? "—"}</Fact>
                {d.amounts.length > 0 ? (
                  // 11-07：原本是表格，手機上要左右捲動；改成一筆一塊，和申請期一樣
                  <ul className="divide-y">
                    {d.amounts.map((a, index) => (
                      <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {`${nameOf(AMOUNT_PERIOD_NAMES, a.period)} ${a.value.toLocaleString("en-US")} ${a.currency}`.trim()}
                          </span>
                          <span>{nameOf(AMOUNT_KIND_NAMES, a.kind)}</span>
                          <Badge variant={a.status === "supported" ? "secondary" : "outline"}>
                            {nameOf(AMOUNT_STATUS_NAMES, a.status)}
                          </Badge>
                        </div>
                        {a.applies_to && <p className="text-muted-foreground">適用：{a.applies_to}</p>}
                        {a.evidence && <p className="max-w-prose text-muted-foreground">「{a.evidence}」</p>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  // 第 9 天改版前抽的資料還沒有金額清單，先顯示原本的文字
                  <Fact label="金額">{d.amount ?? "—"}</Fact>
                )}
              </Section>
              <Section title="要交的文件">
                {/* 11-07：原本是表格，改成一筆一塊，和申請期、補助一樣 */}
                <ul className="divide-y">
                  {d.requirements.map((r, index) => (
                    <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                      <p className="font-medium">
                        {nameOf(DOC_NAMES, r.doc_type)}
                        {r.count && ` ×${r.count}`}
                        {r.required === false && <span className="font-normal text-muted-foreground">（選填）</span>}
                      </p>
                      {r.category && <p className="text-muted-foreground">只限：{r.category}</p>}
                      {r.details && <p className="max-w-prose">{r.details}</p>}
                      {/* 約三成的「要求」和原文引用一字不差，一樣時只顯示一次 */}
                      {r.evidence && r.evidence.trim() !== r.details?.trim() && (
                        <p className="max-w-prose text-muted-foreground">「{r.evidence}」</p>
                      )}
                    </li>
                  ))}
                </ul>
              </Section>
            </>
          )}
        </TabsPanel>
        <TabsPanel value="eligibility">
          {tab === "eligibility" && (
            <>
              <Section title="資格">
                <Fact label="國籍" check={d.nationality_check} quote={d.nationality_evidence}>
                  {nameOf(SCOPE_NAMES, d.nationality_scope)}
                  {d.nationalities.length > 0 && `：${d.nationalities.map((c) => c.name).join("、")}`}
                  {d.nationality_conditions && `（${d.nationality_conditions}）`}
                </Fact>
                <Fact label="可讀學位" check={d.degrees_check} quote={d.degrees_evidence}>
                  {d.degrees.map((degree) => nameOf(DEGREE_NAMES, degree)).join("、") || "原文沒寫"}
                </Fact>
                <Fact label="語言">{d.language_requirements ?? "—"}</Fact>
                <Fact label="其他資格">{d.other_eligibility ?? "—"}</Fact>
                <Fact label="要先錄取">{d.requires_admission === null ? "原文沒說" : d.requires_admission ? "要" : "不用"}</Fact>
                <Fact label="留學國家">{d.countries.map((c) => c.name).join("、") || "—"}</Fact>
                <Fact label="領域">{d.fields.join("、") || "不限或沒寫"}</Fact>
              </Section>
              {d.categories.length > 1 && (
                <Section title="名額類別">
                  {/* 11-08：原本是表格，改成一筆一塊，和申請期、補助、文件一樣（UI 計畫 B6） */}
                  <ul className="divide-y">
                    {d.categories.map((c) => (
                      <li key={c.name} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                        <p className="font-medium">{c.name}</p>
                        <p className="text-muted-foreground">
                          {[`名額 ${c.quota ?? "原文沒寫"}`, c.degrees.map((x) => nameOf(DEGREE_NAMES, x)).join("、")]
                            .filter(Boolean)
                            .join("｜")}
                        </p>
                        {(c.degree_conditions || c.eligibility) && (
                          <p className="max-w-prose">{[c.degree_conditions, c.eligibility].filter(Boolean).join("；")}</p>
                        )}
                        {c.issues.length > 0 && <p className="text-destructive">待確認：{c.issues.map(issueName).join("、")}</p>}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
            </>
          )}
        </TabsPanel>
        <TabsPanel value="score">
          {tab === "score" && (
            <>
              {d.scores.length > 0 ? (
                <Scores detail={d} />
              ) : (
                <p className="text-sm text-muted-foreground">還沒評分：先到「個人資料」填國籍與想讀的學位。</p>
              )}
            </>
          )}
        </TabsPanel>
        <TabsPanel value="history">
          {tab === "history" && (
            <>
              <Section title="變更紀錄">
                {d.changes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">沒有（只列截止日、國籍、學位的變更）</p>
                ) : (
                  <ul className="space-y-1 text-sm">
                    {d.changes.map((c, index) => (
                      <li key={index}>
                        {taipeiTime(c.changed_at)}：{c.text}
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </>
          )}
        </TabsPanel>
      </Tabs>
    </div>
  );
}

// 從列表點進來的用「上一頁」，篩選和捲動位置都保留；直接打開網址的才連到首頁（UI 計畫 A4）
function BackToList() {
  const fromList = (useLocation().state as { fromList?: boolean } | null)?.fromList;
  const navigate = useNavigate();
  return (
    <Link
      to="/"
      onClick={(event) => {
        if (!fromList) return;
        event.preventDefault();
        navigate(-1);
      }}
      className="text-sm text-muted-foreground hover:underline"
    >
      ← 回列表
    </Link>
  );
}

// 頁首的重點摘要（UI 計畫 B2）：申請日期、補助、分數，和列表卡片同一套文字
function Summary({ detail }: { detail: Detail }) {
  const best = detail.scores[0];
  const items = [
    { label: "申請日期", value: detail.deadline_line ?? "原文沒寫" },
    { label: "補助", value: detail.amount_headline ?? "原文沒寫" },
    { label: "你的分數", value: best ? `${Math.round(best.total)} 分` : "未評分" },
  ];
  return (
    <dl className="grid gap-3 rounded-xl bg-muted/50 p-4 text-sm sm:grid-cols-[2fr_1fr_auto]">
      {items.map((item) => (
        <div key={item.label} className="space-y-1">
          <dt className="text-muted-foreground">{item.label}</dt>
          <dd className="font-medium tabular-nums">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// 評分結果的徽章（UI 計畫 B4）：符合灰底、待確認外框、不符合紅色，和列表卡片的徽章一致
const RESULT_VARIANTS = { pass: "secondary", unclear: "outline", fail: "destructive" } as const;

// 只完整顯示分數最高的類別（API 已依分數由高到低排），其他類別各一行
function Scores({ detail }: { detail: Detail }) {
  if (detail.scores.length === 0) return null;
  const [best, ...others] = detail.scores;
  return (
    <Section title="你的評分">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Badge>{Math.round(best.total)} 分</Badge>
          {best.category !== detail.name && <span className="text-sm">{best.category}</span>}
          {best.cap !== null && <span className="text-xs text-muted-foreground">上限 {best.cap}</span>}
        </div>
        <ul className="max-w-prose space-y-1 text-sm">
          {Object.entries(best.checks as Record<string, Check>).map(([name, check]) => (
            <li key={name}>
              {nameOf(CHECK_NAMES, name)}：
              <Badge variant={RESULT_VARIANTS[check.result as keyof typeof RESULT_VARIANTS] ?? "outline"} className="mx-1">
                {nameOf(RESULT_NAMES, check.result)}
              </Badge>
              {check.reason}
            </li>
          ))}
          {Object.entries(best.sub_scores as Record<string, SubScore>).map(([name, sub]) => (
            <li key={name}>
              {nameOf(SUB_SCORE_NAMES, name)}：{sub.score ?? "—"} / 10｜{sub.reason}
            </li>
          ))}
        </ul>
      </div>
      {others.length > 0 && (
        <div className="space-y-1 border-t pt-3 text-sm">
          <p className="font-medium">其他類別</p>
          <ul>
            {others.map((other) => (
              <li key={other.category}>
                {Math.round(other.total)} 分｜{other.category}
                {flagsOf(other).length > 0 && `（${flagsOf(other).join("、")}）`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

function flagsOf(score: Score): string[] {
  return [
    ...score.unclear.map((check) => `${nameOf(CHECK_NAMES, check)}待確認`),
    ...score.failed.map((check) => `${nameOf(CHECK_NAMES, check)}不符合`),
  ];
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">{children}</CardContent>
    </Card>
  );
}

function Fact({
  label,
  check,
  quote,
  children,
}: {
  label: string;
  check?: string | null;
  quote?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="max-w-prose text-sm">
      <span className="font-medium">{label}：</span>
      {children}
      {check && (
        <Badge variant={check === "supported" || check === "catalogue" ? "secondary" : "outline"} className="ml-2">
          {nameOf(VERIFICATION_NAMES, check)}
        </Badge>
      )}
      {quote && <CardDescription className="mt-1">「{quote}」</CardDescription>}
    </div>
  );
}
