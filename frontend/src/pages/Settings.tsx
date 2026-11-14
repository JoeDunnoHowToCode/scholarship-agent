import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageSkeleton } from "@/components/page-skeleton";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { SOURCE_STATUS_NAMES, nameOf, taipeiTime } from "@/lib/labels";

type Settings = Schemas["SettingsOut"];

// 設定頁（第 10 天段 6）：通知門檻、每月 AI 上限、斷路器（ADR-056）、agent 加的來源（ADR-078、095）。
// 畫面上用白話：斷路器 →「AI 自動暫停」、agent 加的來源 →「自動找到的網站」（docs/ui-review-2.md A3）
export default function SettingsPage() {
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: async () => unwrap(await api.GET("/api/settings")),
  });
  if (settings.isPending) return <PageSkeleton />;
  if (settings.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到設定</AlertTitle>
        <AlertDescription>{settings.error.message}</AlertDescription>
      </Alert>
    );
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">設定</h1>
      {/* 用目前的值當 key：存檔後表單用新的值重新開始 */}
      <SettingsForm key={`${settings.data.notify_threshold}-${settings.data.monthly_cap_ntd}`} initial={settings.data} />
      <BreakerCard breaker={settings.data.breaker} />
      <AgentSources />
    </div>
  );
}

function SettingsForm({ initial }: { initial: Settings }) {
  const queryClient = useQueryClient();
  const [threshold, setThreshold] = useState(String(initial.notify_threshold));
  const [cap, setCap] = useState(String(initial.monthly_cap_ntd));
  const save = useMutation({
    mutationFn: async (body: Schemas["SettingsIn"]) => unwrap(await api.PUT("/api/settings", { body })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
      await queryClient.invalidateQueries({ queryKey: ["costs"] });
    },
  });
  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({ notify_threshold: Number(threshold), monthly_cap_ntd: Number(cap) });
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>通知與費用</CardTitle>
        <CardDescription>存檔後，下一次產生通知、下一次呼叫 AI 就照新的設定。</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="threshold">通知門檻（適配度 0–100）</Label>
            <Input id="threshold" type="number" min={0} max={100} value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            <p className="text-xs text-muted-foreground">適配度達到這個分數的獎學金才送 Telegram 通知；設成 0 就全部通知。</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="cap">每月 AI 費用上限（新台幣）</Label>
            <Input id="cap" type="number" min={1} max={initial.cap_limit_ntd} step="1" value={cap} onChange={(e) => setCap(e.target.value)} />
            <p className="text-xs text-muted-foreground">
              最多 NT${initial.cap_limit_ntd.toLocaleString()}；達到上限時 AI 自動暫停並通知你。
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "存檔中…" : "存檔"}
            </Button>
            {save.isSuccess && <span className="text-sm text-muted-foreground">已存檔</span>}
            {save.isError && <span className="text-sm text-destructive">{save.error.message}</span>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function BreakerCard({ breaker }: { breaker: Settings["breaker"] }) {
  const queryClient = useQueryClient();
  const reset = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/settings/breaker/reset")),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          AI 自動暫停
          <Badge variant={breaker.open ? "destructive" : "secondary"}>{breaker.open ? "暫停中" : "正常運作"}</Badge>
        </CardTitle>
        <CardDescription>
          額度用完、金鑰有問題、或達到每月上限時，AI 會自動暫停；暫停時每天只抓網頁、不呼叫 AI。
        </CardDescription>
      </CardHeader>
      {breaker.open && (
        <CardContent className="space-y-3 text-sm">
          <p>
            {taipeiTime(breaker.opened_at)} 打開：{breaker.reason}
          </p>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => reset.mutate()} disabled={reset.isPending}>
              處理好了，恢復 AI
            </Button>
            {reset.isError && <span className="text-destructive">{reset.error.message}</span>}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

function AgentSources() {
  const queryClient = useQueryClient();
  const sources = useQuery({
    queryKey: ["agent-sources"],
    queryFn: async () => unwrap(await api.GET("/api/discovery/sources")),
  });
  const toggle = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) =>
      unwrap(await api.PATCH("/api/discovery/sources/{source_id}", { params: { path: { source_id: id } }, body: { enabled } })),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["agent-sources"] }),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>自動找到的網站</CardTitle>
        <CardDescription>
          AI 自動找到、經規則評分後加入的獎學金網站，以及被停用的網站（例如目錄換了新網址）。看到不對的就關掉；關掉的可以再打開。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {sources.isPending && <Skeleton className="h-24 w-full" />}
        {sources.isError && <p className="text-sm text-destructive">{sources.error.message}</p>}
        {sources.data?.length === 0 && <p className="text-sm text-muted-foreground">還沒有</p>}
        {toggle.isError && <p className="text-sm text-destructive">{toggle.error.message}</p>}
        {sources.data?.map((s) => (
          <div key={s.id} className="flex items-start justify-between gap-4 border-b pb-3 last:border-b-0">
            <div className="min-w-0 space-y-1 text-sm">
              <p className="font-medium">{s.name}</p>
              <a href={s.url} target="_blank" rel="noreferrer" className="wrap-anywhere text-xs text-primary hover:underline">
                {s.url}
              </a>
              <p className="text-xs text-muted-foreground">
                {nameOf(SOURCE_STATUS_NAMES, s.status)}｜獎學金 {s.scholarships} 筆｜提交於 {taipeiTime(s.created_at)}
                {s.review_note && `｜${s.review_note}`}
              </p>
            </div>
            <Switch
              checked={s.enabled}
              disabled={toggle.isPending}
              aria-label={`${s.enabled ? "停用" : "恢復"} ${s.name}`}
              onCheckedChange={(enabled) => toggle.mutate({ id: s.id, enabled })}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
