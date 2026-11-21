import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/page-skeleton";
import { Tabs, TabsList, TabsPanel, TabsTab } from "@/components/ui/tabs";
import {
  AMOUNT_KIND_NAMES,
  AMOUNT_MISMATCH,
  AMOUNT_PERIOD_NAMES,
  CHECK_NAMES,
  DEGREE_LABELS,
  DOC_NAMES,
  FUNDING_NAMES,
  HOW_TO_APPLY_NAMES,
  OTHER_DATE_NAMES,
  RESULT_NAMES,
  SCOPE_NAMES,
  SUB_SCORE_NAMES,
  issueName,
  nameOf,
  shortUrl,
  taipeiTime,
  verificationNote,
} from "@/lib/labels";
import { cn } from "@/lib/utils";

type Detail = Schemas["ScholarshipDetail"];
type Cycle = Schemas["CycleOut"];
type Score = Schemas["ScoreOut"];
type Check = { result: string; reason: string };
type SubScore = { score: number | null; reason: string };

const TABS = [
  { value: "apply", label: "申請" },
  { value: "eligibility", label: "資格" },
  { value: "score", label: "評分" },
  { value: "history", label: "變更" }, // 原本叫「紀錄」，和導覽列的「紀錄」（AI 費用）撞名（docs/ui-review-2.md C5）
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

  if (detail.isPending) return <PageSkeleton cards={2} />;
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
          {(d.stale || d.status === "archived" || d.offered === "no") && (
            <div className="flex flex-wrap gap-2">
              {d.stale && <Badge variant="destructive">{STALE}</Badge>}
              {d.status === "archived" && <Badge variant="secondary">已封存</Badge>}
              {/* ADR-105：原文寫明這次不提供 */}
              {d.offered === "no" && <Badge variant="destructive">這次不提供</Badge>}
            </div>
          )}
          {d.offered === "no" && d.offered_evidence && (
            <p className="max-w-prose text-sm text-muted-foreground">「{d.offered_evidence}」</p>
          )}
        </div>
        {d.official_url && (
          <div className="space-y-1 sm:text-right">
            <a
              href={d.official_url}
              target="_blank"
              rel="noreferrer"
              className={cn(buttonVariants({ size: "lg" }), "w-full sm:w-auto")}
            >
              前往官方網站 ↗
            </a>
            {/* ADR-113：連到的是哪一頁（學程首頁或申請頁），點之前就看得出來 */}
            <p className="wrap-anywhere text-xs text-muted-foreground">{shortUrl(d.official_url)}</p>
          </div>
        )}
      </div>
      <Summary detail={d} />
      {/* 獎學金說明（docs/summary-plan.md）：每句中文附原文引用；只顯示通過核對的句子，一句都沒有就不顯示 */}
      {d.summary.length > 0 && (
        <Card>
          <CardHeader>
            {/* E2 B（ADR-107）：原文寫明這次不提供時，說明與補助是過去的資訊 */}
            <CardTitle>說明{d.offered === "no" && "（過去的資訊）"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {d.summary.map((s, index) => (
              <div key={index} className="space-y-1">
                <p>{s.text}</p>
                <p className="max-w-prose text-xs text-muted-foreground">原文引用：「{s.evidence}」</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
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
                <CycleList cycles={d.cycles.filter((c) => c.status !== "closed")} />
                {/* ADR-119：沒有申請期時照實寫原因（程式依抽取結果判斷），不用假的日期繞過 */}
                {d.cycles.length === 0 && (
                  <p className="text-sm text-muted-foreground">{d.no_date_text ?? "官網這幾頁都沒寫截止日，請看官網"}</p>
                )}
                {d.cycles.length > 0 && d.cycles.every((c) => c.status === "closed") && (
                  <p className="text-sm text-muted-foreground">目前沒有開放中或即將開放的申請期</p>
                )}
                {/* B1 B（ADR-107）：下一屆還沒公布日期時，原文怎麼說 */}
                {d.next_cycle_note && !d.cycles.some((c) => c.status === "open" || c.status === "upcoming") && (
                  <div className="space-y-1 text-sm">
                    <p>下一屆：{d.next_cycle_note}</p>
                    <Quote text={d.next_cycle_evidence} open={false} />
                  </div>
                )}
                {/* 已截止的收起來（docs/ui-review-2.md C1）：只在對照往年時間時有用，不該排在最前面 */}
                {d.cycles.some((c) => c.status === "closed") && (
                  <details className="group border-t pt-3 text-sm">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      過去的申請期（{d.cycles.filter((c) => c.status === "closed").length}）
                    </summary>
                    <div className="pt-3">
                      <CycleList cycles={d.cycles.filter((c) => c.status === "closed")} />
                    </div>
                  </details>
                )}
              </Section>
              {/* ADR-105：補件、繳費、只有入學的日期不算申請期，另外列出來；分類錯了也看得到 */}
              {d.other_dates.length > 0 && (
                <Section title="學校的其他日期（入學申請、繳費等），不是獎學金的截止日">
                  <ul className="divide-y">
                    {d.other_dates.map((o, index) => (
                      <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                        <p className="font-medium">
                          {[o.closes ?? "官網沒寫完整日期", nameOf(OTHER_DATE_NAMES, o.kind), o.label].filter(Boolean).join("｜")}
                        </p>
                        <Quote text={o.evidence} />
                      </li>
                    ))}
                  </ul>
                </Section>
              )}
              <Section title={d.offered === "no" ? "補助（過去的資訊）" : "補助"}>
                <Fact label="補助內容">{d.coverage ?? "—"}</Fact>
                {d.amounts.length > 0 ? (
                  // 11-07：原本是表格，手機上要左右捲動；改成一筆一塊，和申請期一樣
                  <ul className="divide-y">
                    {d.amounts.map((a, index) => (
                      <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {`${nameOf(AMOUNT_PERIOD_NAMES, a.period)} ${amountText(a)}`.trim()}
                          </span>
                          <span>{nameOf(AMOUNT_KIND_NAMES, a.kind)}</span>
                        </div>
                        {/* 段 9：核對通過的不標；沒通過的寫一句話，原文直接展開 */}
                        {a.status && a.status !== "supported" && <Warning>{AMOUNT_MISMATCH}</Warning>}
                        {a.applies_to && <p className="text-muted-foreground">適用：{a.applies_to}</p>}
                        <Quote text={a.evidence} open={Boolean(a.status) && a.status !== "supported"} />
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
                {d.requirements.length === 0 && (
                  <p className="text-sm text-muted-foreground">原文沒有列出要交的文件，請看官方網站。</p>
                )}
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
                      {r.evidence?.trim() !== r.details?.trim() && <Quote text={r.evidence} />}
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
                  <Nationality detail={d} />
                </Fact>
                <Fact label="可讀學位" check={d.degrees_check} quote={d.degrees_evidence}>
                  {d.degrees.map((degree) => nameOf(DEGREE_LABELS, degree)).join("、") || "原文沒寫"}
                </Fact>
                <Fact label="語言">{d.language_requirements ?? "—"}</Fact>
                <Fact label="其他資格">{d.other_eligibility ?? "—"}</Fact>
                <Fact label="申請方式" check={d.how_to_apply_check} quote={d.how_to_apply_evidence}>
                  {howToApply(d, true)}
                </Fact>
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
                          {[`名額 ${c.quota ?? "原文沒寫"}`, c.degrees.map((x) => nameOf(DEGREE_LABELS, x)).join("、")]
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
    { label: "申請日期", value: detail.deadline_line ?? detail.no_date_text ?? "官網沒寫" },
    { label: "補助", value: detail.amount_headline ?? "原文沒寫" },
    { label: "你的分數", value: best ? `${Math.round(best.total)} 分` : "未評分" },
    // 決定要先申請學校還是先申請獎學金，從「資格」頁籤提到這裡（docs/ui-review-2.md C6）；段 9 改成申請方式（ADR-119）
    { label: "申請方式", value: howToApply(detail) },
  ];
  return (
    <dl className="grid gap-3 rounded-xl bg-muted/50 p-4 text-sm sm:grid-cols-[2fr_1fr_auto_1.5fr]">
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
          {best.cap !== null && <span className="text-xs text-muted-foreground">{capText(best)}</span>}
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

// 分數上限（ADR-059）的原因：不符合最多 20 分、待確認最多 80 分（段 9：不寫「上限 80」這種內部機制）
function capText(score: Score): string {
  const checks = (list: string[]) => list.map((check) => nameOf(CHECK_NAMES, check)).join("、");
  if (score.failed.length > 0) return `因為${checks(score.failed)}不符合，分數最多算到 ${score.cap}`;
  if (score.unclear.length > 0) return `因為${checks(score.unclear)}還不確定，分數最多算到 ${score.cap}`;
  return `分數最多算到 ${score.cap}`;
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
      {/* 段 9：核對通過的不標；依目錄的寫小字；沒通過的寫一句話，原文直接展開 */}
      {check === "catalogue" ? (
        <span className="ml-2 text-xs text-muted-foreground">（{verificationNote(check)}）</span>
      ) : (
        verificationNote(check) && <Warning>{verificationNote(check)}</Warning>
      )}
      <Quote text={quote} open={Boolean(verificationNote(check)) && check !== "catalogue"} />
    </div>
  );
}

// 申請期一期一塊：第一行是日期與狀態，第二行是適用對象與核對結果，下面是原文引用
// 一筆錢的數字：「1,400 EUR」「減免 50%」，兩個都有時「4,500 EUR（減免 50%）」（ADR-107 C1 B）
function amountText(a: { value: number | null; percent?: number | null; currency: string }): string {
  const percent = a.percent != null ? `減免 ${a.percent}%` : null;
  if (a.value == null) return percent ?? "";
  const number = `${a.value.toLocaleString("en-US")} ${a.currency}`;
  return percent ? `${number}（${percent}）` : number;
}

function CycleList({ cycles }: { cycles: Cycle[] }) {
  return (
    <ul className="divide-y">
      {cycles.map((c, index) => (
        <li key={index} className="space-y-1 py-3 text-sm first:pt-0 last:pb-0">
          {/* 例如「2026-10-20 → 2027-01-11（開放中）Grant application period」：狀態已經在括號裡 */}
          <p className="font-medium">{c.description}</p>
          <p className="text-muted-foreground">
            {[
              // 原文沒寫時區時，存的是 UTC+14 的當天結束，換成台灣時間的時刻（例如 17:59）是假的，不顯示（docs/ui-review-2.md C4）
              !c.timezone_assumed && `台灣時間 ${taipeiTime(c.closes_at)} 截止`,
              cycleScope(c),
              FUNDING_NAMES[c.funding] ?? c.funding,
            ]
              .filter(Boolean)
              .join("｜")}
          </p>
          {/* 預估的申請期，evidence 是推估的說明（例如「依 2022 年的日期推估」），不是原文引用 */}
          {!c.estimated && verificationNote(c.verification) && <Warning>{verificationNote(c.verification)}</Warning>}
          {c.estimated ? (
            c.evidence && <p className="text-muted-foreground">{c.evidence}</p>
          ) : (
            <Quote text={c.evidence} open={Boolean(verificationNote(c.verification))} />
          )}
        </li>
      ))}
    </ul>
  );
}

// 原文引用（ADR-106）：核對沒通過的直接顯示，最需要你看原文；已核對或沒有核對結果的收起成「原文 ▸」，點了才展開。
// 用原生的 <details>：鍵盤和螢幕閱讀器都能用，Chrome 的 ⌘F 也會自動展開找到的段落
function Quote({ text, open = false }: { text: string | null | undefined; open?: boolean }) {
  if (!text) return null;
  if (open) return <p className="max-w-prose text-sm text-muted-foreground">「{text}」</p>;
  return (
    <details className="group max-w-prose text-sm text-muted-foreground">
      <summary className="w-fit cursor-pointer list-none text-xs hover:text-foreground [&::-webkit-details-marker]:hidden">
        原文 <span className="inline-block transition-transform group-open:rotate-90">▸</span>
      </summary>
      <p className="mt-1">「{text}」</p>
    </details>
  );
}

// 申請方式：AI 有答、但和原文對不上（被改成 unclear）時，不是「官網沒寫」，要你看原文
function howToApply(detail: Detail, onEligibilityTab = false): string {
  if (detail.how_to_apply === "unclear" && verificationNote(detail.how_to_apply_check))
    return onEligibilityTab ? "AI 讀不出確定的申請方式" : "AI 讀不出確定的申請方式，請看「資格」頁的原文";
  return nameOf(HOW_TO_APPLY_NAMES, detail.how_to_apply);
}

// 段 9：「資料過舊」看不出多舊；ADR-058 的判斷是最近一次截止日超過兩年
const STALE = "最近一次截止日在兩年前，官網可能沒更新";

// 核對沒通過、要你看原文的一句話
function Warning({ children }: { children: ReactNode }) {
  return <p className="text-xs text-amber-700 dark:text-amber-400">⚠ {children}</p>;
}

// 申請期適用的國籍：不用自己數「列出的國家以外（27 國）」是哪些國家
function cycleScope(c: Cycle): string {
  const count = c.nationalities.length;
  if (c.nationality_scope === "excluded" && count > 0) return `除了 ${count} 個國家，其他國籍都可以`;
  if (c.nationality_scope === "listed" && count > 0) return `只限 ${count} 個國家`;
  return nameOf(SCOPE_NAMES, c.nationality_scope);
}

// 獎學金的國籍：寫成群組時先寫群組名稱（例如「除了歐盟、歐洲經濟區」），國家清單點開才看（段 9）
function Nationality({ detail }: { detail: Detail }) {
  const names = detail.nationalities.map((c) => c.name);
  const groups = detail.nationality_groups.join("、");
  const scope = detail.nationality_scope;
  let text = nameOf(SCOPE_NAMES, scope);
  if (scope === "excluded" && groups) text = `除了${groups}，其他國籍都可以`;
  if (scope === "listed" && groups) text = `只限${groups}`;
  const list = names.join("、");
  return (
    <>
      {text}
      {detail.nationality_conditions && `（${detail.nationality_conditions}）`}
      {names.length > 0 &&
        (names.length <= 5 && !groups ? (
          `：${list}`
        ) : (
          <details className="mt-1 text-muted-foreground">
            <summary className="w-fit cursor-pointer text-xs hover:text-foreground">看 {names.length} 個國家</summary>
            <p className="mt-1">{list}</p>
          </details>
        ))}
    </>
  );
}
