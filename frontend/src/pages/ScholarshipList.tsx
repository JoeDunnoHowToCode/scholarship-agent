import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { CHECK_NAMES, DEGREE_NAMES, GROUP_NAMES, nameOf, taipeiTime } from "@/lib/labels";

type Row = Schemas["ScholarshipRow"];
type Degree = "bachelor" | "master" | "phd";

// 下拉選單的「全部」：API 收到時當成沒有篩選
const ALL = "all";

type Filters = { country: string; degree: string; openOnly: boolean; after: string; before: string };

const DEGREE_ITEMS = [
  { value: ALL, label: "所有學位" },
  ...Object.entries(DEGREE_NAMES).map(([value, label]) => ({ value, label })),
];

export default function ScholarshipList() {
  const [filters, setFilters] = useState<Filters>({
    country: ALL,
    degree: ALL,
    openOnly: false,
    after: "",
    before: "",
  });
  // 沒填的條件不送（undefined 不會出現在網址上）
  const query = {
    country: filters.country === ALL ? undefined : filters.country,
    degree: filters.degree === ALL ? undefined : (filters.degree as Degree),
    open_only: filters.openOnly || undefined,
    deadline_after: filters.after || undefined,
    deadline_before: filters.before || undefined,
  };
  const list = useQuery({
    queryKey: ["scholarships", query],
    queryFn: async () => unwrap(await api.GET("/api/scholarships", { params: { query } })),
    // 個人資料改過、評分還在背景更新時，每 5 秒重抓一次，直到更新完
    refetchInterval: (current) => (current.state.data?.scores_outdated ? 5000 : false),
  });
  // 國家選單用全部獎學金的國家，不受目前的篩選影響（和沒有篩選的列表共用快取）
  const everything = useQuery({
    queryKey: ["scholarships", {}],
    queryFn: async () => unwrap(await api.GET("/api/scholarships")),
  });
  const countryItems = [{ value: ALL, label: "所有國家" }, ...countriesOf(everything.data?.rows ?? [])];
  const update = (change: Partial<Filters>) => setFilters((current) => ({ ...current, ...change }));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">獎學金</h1>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1">
          <Label>留學國家</Label>
          <Select items={countryItems} value={filters.country} onValueChange={(value) => update({ country: value ?? ALL })}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {countryItems.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label>學位</Label>
          <Select items={DEGREE_ITEMS} value={filters.degree} onValueChange={(value) => update({ degree: value ?? ALL })}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DEGREE_ITEMS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="after">截止日從</Label>
          <Input id="after" type="date" value={filters.after} onChange={(event) => update({ after: event.target.value })} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="before">截止日到</Label>
          <Input id="before" type="date" value={filters.before} onChange={(event) => update({ before: event.target.value })} />
        </div>
        <Label className="flex items-center gap-2 pb-2">
          <Switch checked={filters.openOnly} onCheckedChange={(checked) => update({ openOnly: checked })} />
          只看還能申請的
        </Label>
      </div>

      {list.data?.scores_outdated && (
        <Alert>
          <AlertTitle>評分更新中</AlertTitle>
          <AlertDescription>個人資料改過了，評分正在背景重新計算，完成後這裡會自動更新。</AlertDescription>
        </Alert>
      )}
      {list.isError && (
        <Alert variant="destructive">
          <AlertTitle>讀不到獎學金</AlertTitle>
          <AlertDescription>{list.error.message}</AlertDescription>
        </Alert>
      )}
      {list.isPending && <Skeleton className="h-40 w-full" />}
      {list.data && <p className="text-sm text-muted-foreground">共 {list.data.rows.length} 筆</p>}
      {list.data?.rows.length === 0 && <p className="text-sm">沒有符合條件的獎學金，可以放寬篩選條件再試。</p>}
      {list.data?.rows.map((row, index) => (
        <div key={row.id} className="space-y-2">
          {/* 時間狀態換了就寫一個分組標題（列表已經依時間狀態、分數排好） */}
          {(index === 0 || list.data.rows[index - 1].group !== row.group) && (
            <h2 className="pt-4 text-base font-semibold">{row.group ? GROUP_NAMES[row.group] : "還沒評分"}</h2>
          )}
          <ScholarshipCard row={row} />
        </div>
      ))}
    </div>
  );
}

function ScholarshipCard({ row }: { row: Row }) {
  const flags = [
    ...row.unclear.map((check) => `${nameOf(CHECK_NAMES, check)}待確認`),
    ...row.failed.map((check) => `${nameOf(CHECK_NAMES, check)}不符合`),
  ];
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>
          <Link to={`/scholarships/${row.id}`} className="hover:underline">
            {row.name}
          </Link>
        </CardTitle>
        <CardDescription>{[row.name_zh, row.provider].filter(Boolean).join("｜")}</CardDescription>
        <CardAction>
          <Badge variant={row.score === null ? "outline" : "default"}>
            {row.score === null ? "未評分" : `${Math.round(row.score)} 分`}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex flex-wrap gap-2">
          {row.stale && <Badge variant="destructive">資料過舊</Badge>}
          {row.status === "archived" && <Badge variant="secondary">已封存</Badge>}
          {flags.map((flag) => (
            <Badge key={flag} variant="outline">
              {flag}
            </Badge>
          ))}
          <span className="text-muted-foreground">
            {row.degrees.map((degree) => nameOf(DEGREE_NAMES, degree)).join("、")}｜
            {row.countries.map((country) => country.name).join("、") || "國家沒寫"}
          </span>
        </div>
        {row.time_reason && <p>{row.time_reason}</p>}
        {row.next_deadline && <p className="text-muted-foreground">最近的截止：{taipeiTime(row.next_deadline)}</p>}
        {row.category && row.category !== row.name && (
          <p className="text-muted-foreground">分數來自類別：{row.category}</p>
        )}
      </CardContent>
    </Card>
  );
}

// 所有獎學金出現過的國家，依中文名稱排序
function countriesOf(rows: Row[]): { value: string; label: string }[] {
  const names = new Map<string, string>();
  for (const row of rows) for (const country of row.countries) names.set(country.code, country.name);
  return [...names]
    .map(([value, label]) => ({ value, label }))
    .sort((a, b) => a.label.localeCompare(b.label, "zh-Hant"));
}
