import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, unwrap } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/page-skeleton";
import { Skeleton } from "@/components/ui/skeleton";
import { AGENT_RESULT_NAMES, AGENT_TASK_NAMES, FEATURE_NAMES, nameOf, taipeiTime } from "@/lib/labels";

// agent 用的工具（backend/prompts/tool-*）
const TOOL_NAMES: Record<string, string> = { search: "搜尋", read_page: "讀網頁", submit: "提交結果" };

const ntd = (value: number) => `NT$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

// 紀錄頁（第 10 天段 6，ADR-089）：本月 AI 費用、依功能分、最近 7 天，以及 agent 每一次執行做了什麼
export default function Logs() {
  const costs = useQuery({ queryKey: ["costs"], queryFn: async () => unwrap(await api.GET("/api/costs")) });
  const runs = useQuery({
    queryKey: ["agent-runs"],
    queryFn: async () => unwrap(await api.GET("/api/agent-runs", { params: { query: { limit: 30 } } })),
  });
  if (costs.isPending) return <PageSkeleton cards={2} />;
  if (costs.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到費用紀錄</AlertTitle>
        <AlertDescription>{costs.error.message}</AlertDescription>
      </Alert>
    );
  const used = costs.data.cap_ntd > 0 ? Math.min(100, (costs.data.month_ntd / costs.data.cap_ntd) * 100) : 0;
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">紀錄</h1>
      <Card>
        <CardHeader>
          <CardTitle>本月 AI 費用</CardTitle>
          <CardDescription>以台灣時間的月份計算；每次 AI 呼叫都記一筆。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-lg font-semibold">
            {ntd(costs.data.month_ntd)} <span className="text-sm font-normal text-muted-foreground">／ 上限 {ntd(costs.data.cap_ntd)}</span>
          </p>
          <div className="h-2 w-full rounded bg-muted" role="progressbar" aria-valuenow={Math.round(used)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2 rounded bg-primary" style={{ width: `${used}%` }} />
          </div>
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <p className="mb-1 font-medium">依功能（本月）</p>
              {costs.data.by_feature.map((f) => (
                <p key={f.feature} className="flex justify-between">
                  <span>{nameOf(FEATURE_NAMES, f.feature)}（{f.calls} 次）</span>
                  <span className="tabular-nums">{ntd(f.ntd)}</span>
                </p>
              ))}
            </div>
            <div>
              <p className="mb-1 font-medium">最近 7 天</p>
              {costs.data.by_day.map((d) => (
                <p key={d.day} className="flex justify-between">
                  <span>{d.day.slice(5)}</span>
                  <span className="tabular-nums">{ntd(d.ntd)}</span>
                </p>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>自動找網站的紀錄</CardTitle>
          <CardDescription>最近 30 次；點「看每一步」看它搜了什麼、打開了哪些網頁。全文只留 30 天，之後只剩摘要。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {runs.isPending && <Skeleton className="h-24 w-full" />}
          {runs.isError && <p className="text-sm text-destructive">{runs.error.message}</p>}
          {runs.data?.length === 0 && <p className="text-sm text-muted-foreground">還沒有</p>}
          {runs.data?.map((run) => <RunRow key={run.id} run={run} />)}
        </CardContent>
      </Card>
    </div>
  );
}

function RunRow({ run }: { run: { id: number; task: string; target: string | null; started_at: string; result: string | null; steps: number; ntd: number; final_text: string | null } }) {
  const [open, setOpen] = useState(false);
  const steps = useQuery({
    queryKey: ["agent-steps", run.id],
    queryFn: async () => unwrap(await api.GET("/api/agent-runs/{run_id}/steps", { params: { path: { run_id: run.id } } })),
    enabled: open, // 點開才抓
  });
  return (
    <div className="space-y-2 border-b pb-3 text-sm last:border-b-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{nameOf(AGENT_TASK_NAMES, run.task)}</span>
        <Badge variant={run.result === "done" ? "secondary" : run.result === "error" ? "destructive" : "outline"}>
          {run.result ? nameOf(AGENT_RESULT_NAMES, run.result) : "進行中"}
        </Badge>
        <span className="text-muted-foreground">
          {taipeiTime(run.started_at)}｜{run.steps} 步｜{ntd(run.ntd)}
          {run.target && `｜${run.target}`}
        </span>
        <Button variant="ghost" size="sm" onClick={() => setOpen(!open)}>
          {open ? "收起" : "看每一步"}
        </Button>
      </div>
      {run.final_text && <p className="text-muted-foreground">{run.final_text}</p>}
      {open && (
        <div className="space-y-2 rounded bg-muted/50 p-3">
          {steps.isPending && <Skeleton className="h-16 w-full" />}
          {steps.data?.map((step, index) => (
            <div key={index}>
              <p className="text-xs font-medium">
                第 {step.number} 步・{step.kind === "tool" ? nameOf(TOOL_NAMES, step.tool) : "AI 回覆"}
                {/* 工具的參數只列值（例如搜尋字、網址），不顯示 JSON */}
                {step.args && <span className="font-normal text-muted-foreground">　{Object.values(step.args).map(String).join("、")}</span>}
              </p>
              <p className="wrap-anywhere whitespace-pre-wrap text-xs text-muted-foreground">{step.full_text ?? step.summary}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
