import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EVENT_KIND_NAMES, EVENT_STATUS_NAMES, nameOf, taipeiTime } from "@/lib/labels";

export default function Notifications() {
  const events = useQuery({
    queryKey: ["events"],
    queryFn: async () => unwrap(await api.GET("/api/events", { params: { query: { limit: 50 } } })),
  });
  if (events.isPending) return <Skeleton className="h-60 w-full" />;
  if (events.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到通知</AlertTitle>
        <AlertDescription>{events.error.message}</AlertDescription>
      </Alert>
    );
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">通知歷史</h1>
      <p className="text-sm text-muted-foreground">最近 50 則；第一次啟用時記下、沒有送出的基準線不列。</p>
      {events.data.length === 0 && <p className="text-sm text-muted-foreground">還沒有通知</p>}
      {events.data.map((e) => (
        <Card key={e.id} size="sm">
          <CardHeader>
            <CardTitle>{e.title}</CardTitle>
            <CardDescription>
              {nameOf(EVENT_KIND_NAMES, e.kind)}｜產生於 {taipeiTime(e.created_at)}
              {e.sent_at && `｜送出於 ${taipeiTime(e.sent_at)}`}
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
                <a href={e.url} target="_blank" rel="noreferrer" className="break-all text-primary hover:underline">
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
