import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AMOUNT_KIND_NAMES,
  AMOUNT_PERIOD_NAMES,
  AMOUNT_STATUS_NAMES,
  CHECK_NAMES,
  CYCLE_STATUS_NAMES,
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

type Detail = Schemas["ScholarshipDetail"];
type Score = Schemas["ScoreOut"];
type Check = { result: string; reason: string };
type SubScore = { score: number | null; reason: string };

export default function ScholarshipDetail() {
  const id = Number(useParams().id);
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
      <Link to="/" className="text-sm text-muted-foreground hover:underline">
        ← 回列表
      </Link>
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">{d.name}</h1>
        <p className="text-muted-foreground">{[d.name_zh, d.provider].filter(Boolean).join("｜")}</p>
        <div className="flex flex-wrap gap-2">
          {d.stale && <Badge variant="destructive">資料過舊</Badge>}
          {d.status === "archived" && <Badge variant="secondary">已封存</Badge>}
          {d.official_url && (
            <a href={d.official_url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline">
              官方網站 ↗
            </a>
          )}
        </div>
      </div>
      <Scores detail={d} />
      <Section title="申請期">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>截止日</TableHead>
              <TableHead>狀態</TableHead>
              <TableHead>適用</TableHead>
              <TableHead>原文引用</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.cycles.map((c, index) => (
              <TableRow key={index}>
                <TableCell className="align-top">
                  <div>{c.description}</div>
                  <div className="text-xs text-muted-foreground">{taipeiTime(c.closes_at)}</div>
                </TableCell>
                <TableCell className="align-top">
                  {nameOf(CYCLE_STATUS_NAMES, c.status)}
                  {!c.estimated && <div className="text-xs text-muted-foreground">{nameOf(VERIFICATION_NAMES, c.verification)}</div>}
                </TableCell>
                <TableCell className="align-top whitespace-normal">
                  {nameOf(SCOPE_NAMES, c.nationality_scope)}
                  {c.nationalities.length > 0 && `（${c.nationalities.length} 國）`}｜{nameOf(FUNDING_NAMES, c.funding)}
                </TableCell>
                <TableCell className="align-top whitespace-normal text-muted-foreground">{c.evidence ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {d.cycles.length === 0 && <p className="text-sm text-muted-foreground">原文沒有截止日</p>}
      </Section>
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
      <Section title="補助">
        <Fact label="補助內容">{d.coverage ?? "—"}</Fact>
        {d.amounts.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>金額</TableHead>
                <TableHead>用途</TableHead>
                <TableHead>核對</TableHead>
                <TableHead>原文引用</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.amounts.map((a, index) => (
                <TableRow key={index}>
                  <TableCell className="align-top">
                    {`${nameOf(AMOUNT_PERIOD_NAMES, a.period)} ${a.value.toLocaleString("en-US")} ${a.currency}`.trim()}
                  </TableCell>
                  <TableCell className="align-top whitespace-normal">
                    {nameOf(AMOUNT_KIND_NAMES, a.kind)}
                    {a.applies_to && <div className="text-xs text-muted-foreground">{a.applies_to}</div>}
                  </TableCell>
                  <TableCell className="align-top">
                    <Badge variant={a.status === "supported" ? "secondary" : "outline"}>
                      {nameOf(AMOUNT_STATUS_NAMES, a.status)}
                    </Badge>
                  </TableCell>
                  <TableCell className="align-top whitespace-normal text-muted-foreground">{a.evidence ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          // 第 9 天改版前抽的資料還沒有金額清單，先顯示原本的文字
          <Fact label="金額">{d.amount ?? "—"}</Fact>
        )}
      </Section>
      {d.categories.length > 1 && (
        <Section title="名額類別">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>類別</TableHead>
                <TableHead>名額</TableHead>
                <TableHead>學位</TableHead>
                <TableHead>條件</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.categories.map((c) => (
                <TableRow key={c.name}>
                  <TableCell className="align-top whitespace-normal">
                    {c.name}
                    {c.issues.length > 0 && <div className="text-xs text-destructive">待確認：{c.issues.map(issueName).join("、")}</div>}
                  </TableCell>
                  <TableCell className="align-top">{c.quota ?? "—"}</TableCell>
                  <TableCell className="align-top">{c.degrees.map((x) => nameOf(DEGREE_NAMES, x)).join("、")}</TableCell>
                  <TableCell className="align-top whitespace-normal">
                    {[c.degree_conditions, c.eligibility].filter(Boolean).join("；") || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Section>
      )}
      <Section title="要交的文件">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>文件</TableHead>
              <TableHead>要求</TableHead>
              <TableHead>原文引用</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {d.requirements.map((r, index) => (
              <TableRow key={index}>
                <TableCell className="align-top">
                  {nameOf(DOC_NAMES, r.doc_type)}
                  {r.count && ` ×${r.count}`}
                  {r.required === false && <div className="text-xs text-muted-foreground">選填</div>}
                  {r.category && <div className="text-xs text-muted-foreground">只限：{r.category}</div>}
                </TableCell>
                <TableCell className="align-top whitespace-normal">{r.details ?? "—"}</TableCell>
                <TableCell className="align-top whitespace-normal text-muted-foreground">{r.evidence ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Section>
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
    </div>
  );
}

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
        <ul className="text-sm">
          {Object.entries(best.checks as Record<string, Check>).map(([name, check]) => (
            <li key={name}>
              {nameOf(CHECK_NAMES, name)}：{nameOf(RESULT_NAMES, check.result)}｜{check.reason}
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
    <div className="text-sm">
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
