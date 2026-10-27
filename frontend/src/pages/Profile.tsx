import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DEGREE_NAMES } from "@/lib/labels";

type Profile = Schemas["ProfileOut"];
type Degree = Schemas["ProfileIn"]["target_degree"];
type Save = UseMutationResult<Profile, Error, Schemas["ProfileIn"]>;

const DEGREE_ITEMS = Object.entries(DEGREE_NAMES).map(([value, label]) => ({ value, label }));

export default function ProfilePage() {
  const queryClient = useQueryClient();
  // 存檔放在外層：存檔後版本號變了，表單會重新建立，存檔的結果（已存檔、錯誤）還留著
  const save = useMutation({
    mutationFn: async (body: Schemas["ProfileIn"]) => unwrap(await api.PUT("/api/profile", { body })),
    onSuccess: async () => {
      // 個人資料改了：重抓個人資料與列表（列表會顯示「評分更新中」）
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      await queryClient.invalidateQueries({ queryKey: ["scholarships"] });
    },
  });
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const result = await api.GET("/api/profile");
      if (result.response.status === 404) return null; // 還沒有個人資料：顯示空白表單
      return unwrap(result);
    },
  });
  if (profile.isPending) return <Skeleton className="h-80 w-full" />;
  if (profile.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到個人資料</AlertTitle>
        <AlertDescription>{profile.error.message}</AlertDescription>
      </Alert>
    );
  // 用版本號當 key：存檔後版本號變了，表單就用新的資料重新開始
  return <ProfileForm key={profile.data?.version ?? 0} initial={profile.data} save={save} />;
}

// 清單欄位在表單上用逗號分隔
const toList = (text: string) =>
  text
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);

function ProfileForm({ initial, save }: { initial: Profile | null; save: Save }) {
  const [nationality, setNationality] = useState(initial?.nationality ?? "");
  const [degree, setDegree] = useState<Degree>(initial?.target_degree ?? "master");
  const [major, setMajor] = useState(initial?.current_major ?? "");
  const [fields, setFields] = useState((initial?.target_fields ?? []).join(", "));
  const [countries, setCountries] = useState((initial?.target_countries ?? []).join(", "));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({
      nationality: nationality.trim().toUpperCase(),
      target_degree: degree,
      current_major: major.trim() || null,
      target_fields: toList(fields),
      target_countries: toList(countries).map((code) => code.toUpperCase()),
    });
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle>個人資料</CardTitle>
        <CardDescription>
          只存在這台電腦的資料庫；送給 AI 的只有目前科系與想讀的領域（ADR-055）。存檔後，評分會在背景重新計算。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="nationality">國籍（國碼，必填，例如 TW）</Label>
            <Input id="nationality" value={nationality} onChange={(event) => setNationality(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>想讀的學位（必填）</Label>
            <Select items={DEGREE_ITEMS} value={degree} onValueChange={(value) => value && setDegree(value as Degree)}>
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
            <Label htmlFor="major">目前科系（選填）</Label>
            <Input id="major" value={major} onChange={(event) => setMajor(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="fields">想讀的領域（選填，用逗號分隔）</Label>
            <Input id="fields" value={fields} onChange={(event) => setFields(event.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="countries">想去的國家（選填，國碼用逗號分隔，例如 SE, FI, NL）</Label>
            <Input id="countries" value={countries} onChange={(event) => setCountries(event.target.value)} />
          </div>
          {save.isError && (
            <Alert variant="destructive">
              <AlertTitle>沒有存檔</AlertTitle>
              <AlertDescription>{save.error.message}</AlertDescription>
            </Alert>
          )}
          {save.isSuccess && <p className="text-sm text-muted-foreground">已存檔（版本 {save.data.version}）</p>}
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "存檔中…" : "存檔"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
