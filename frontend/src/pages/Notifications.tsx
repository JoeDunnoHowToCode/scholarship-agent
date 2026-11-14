import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, unwrap } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSkeleton } from "@/components/page-skeleton";
import { Tabs, TabsList, TabsTab } from "@/components/ui/tabs";
import { EVENT_KIND_NAMES, EVENT_STATUS_NAMES, nameOf, taipeiTime } from "@/lib/labels";

// 每日檢查報告這類系統通知和獎學金通知分開看（docs/ui-review-2.md D1）；選到的記在網址 ?kind=
const KINDS = [
  { value: "all", label: "全部" },
  { value: "scholarship", label: "獎學金" },
  { value: "system", label: "系統" },
];

export default function Notifications() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const kind = KINDS.find((k) => k.value === params.get("kind"))?.value ?? "all";
  const events = useQuery({
    queryKey: ["events"],
    queryFn: async () => unwrap(await api.GET("/api/events", { params: { query: { limit: 50 } } })),
  });
  if (events.isPending) return <PageSkeleton />;
  if (events.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到通知</AlertTitle>
        <AlertDescription>{events.error.message}</AlertDescription>
      </Alert>
    );
  const shown = events.data.filter((e) => kind === "all" || (kind === "system") === (e.kind === "system"));
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">通知歷史</h1>
      {/* 第一次啟用時記下、沒有送出的基準線不列（ADR-062） */}
      <p className="text-sm text-muted-foreground">最近 50 則。</p>
      <Tabs value={kind} onValueChange={(value) => setParams(value === "all" ? {} : { kind: String(value) }, { replace: true })}>
        <TabsList>
          {KINDS.map((k) => (
            <TabsTab key={k.value} value={k.value}>
              {k.label}
            </TabsTab>
          ))}
        </TabsList>
      </Tabs>
      {shown.length === 0 && <p className="text-sm text-muted-foreground">還沒有通知</p>}
      {shown.map((e) => (
        <Card
          key={e.id}
          size="sm"
          // 和某一筆獎學金有關的通知整張卡片可點，做法和列表卡片一樣（docs/ui-review-2.md D2、ADR-092）；鍵盤用標題連結
          onClick={
            e.scholarship_id
              ? () => {
                  if (window.getSelection()?.toString()) return; // 正在選取文字時不換頁
                  navigate(`/scholarships/${e.scholarship_id}`);
                }
              : undefined
          }
          className={
            e.scholarship_id
              ? "cursor-pointer transition-colors hover:bg-muted/50 has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-ring"
              : undefined
          }
        >
          <CardHeader>
            <CardTitle>
              {e.scholarship_id ? (
                <Link to={`/scholarships/${e.scholarship_id}`} onClick={(event) => event.stopPropagation()} className="outline-none">
                  {e.title}
                </Link>
              ) : (
                e.title
              )}
            </CardTitle>
            {/* 只寫一個時間：送出了寫送出時間，還沒送寫產生時間（兩個通常只差幾秒） */}
            <CardDescription>
              {nameOf(EVENT_KIND_NAMES, e.kind)}｜{e.sent_at ? `送出於 ${taipeiTime(e.sent_at)}` : `產生於 ${taipeiTime(e.created_at)}`}
            </CardDescription>
            <CardAction>
              <Badge variant={e.status === "sent" ? "secondary" : e.status === "failed" ? "destructive" : "outline"}>
                {nameOf(EVENT_STATUS_NAMES, e.status)}
              </Badge>
            </CardAction>
          </CardHeader>
          {(e.lines.length > 0 || e.url) && (
            <CardContent className="space-y-1 text-sm">
              {e.lines.map((line, index) => (
                <p key={index}>{line}</p>
              ))}
              {e.url && (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(event) => event.stopPropagation()}
                  className="wrap-anywhere text-primary hover:underline"
                >
                  {e.url}
                </a>
              )}
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}
