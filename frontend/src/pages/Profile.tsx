import { useMutation, useQuery, useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { api, unwrap, type Schemas } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CountryMultiSelect, CountrySelect, type CountryOption } from "@/components/country-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { TagInput } from "@/components/tag-input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PageSkeleton } from "@/components/page-skeleton";
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
  // 國家選單的完整清單（ADR-091），依中文名稱排序
  const countries = useQuery({
    queryKey: ["countries"],
    queryFn: async () => unwrap(await api.GET("/api/profile/countries")),
    select: (rows) => [...rows].sort((a, b) => a.name.localeCompare(b.name, "zh-Hant")),
    staleTime: Infinity,
  });
  if (profile.isPending || countries.isPending) return <PageSkeleton cards={1} />;
  if (countries.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到國家清單</AlertTitle>
        <AlertDescription>{countries.error.message}</AlertDescription>
      </Alert>
    );
  if (profile.isError)
    return (
      <Alert variant="destructive">
        <AlertTitle>讀不到個人資料</AlertTitle>
        <AlertDescription>{profile.error.message}</AlertDescription>
      </Alert>
    );
  // 用版本號當 key：存檔後版本號變了，表單就用新的資料重新開始
  return (
    <div className="space-y-4">
      {/* 每頁一個頁面標題，和其他頁一致（docs/ui-review-2.md D4） */}
      <h1 className="text-xl font-semibold">個人資料</h1>
      <ProfileForm key={profile.data?.version ?? 0} initial={profile.data} save={save} countries={countries.data} />
    </div>
  );
}

const sameList = (a: string[], b: string[]) => a.length === b.length && a.every((item, index) => item === b[index]);

function ProfileForm({ initial, save, countries }: { initial: Profile | null; save: Save; countries: CountryOption[] }) {
  // 表單裡存國碼；選單要的是 { 國碼, 中文名稱 }，用國碼查回來
  const byCode = new Map(countries.map((c) => [c.code, c]));
  const optionsOf = (codes: string[]) => codes.map((code) => byCode.get(code) ?? { code, name: code });
  const [nationality, setNationality] = useState(initial?.nationality ?? "");
  const [degree, setDegree] = useState<Degree>(initial?.target_degree ?? "master");
  const [major, setMajor] = useState(initial?.current_major ?? "");
  const [fields, setFields] = useState<string[]>(initial?.target_fields ?? []);
  const [targets, setTargets] = useState<string[]>(initial?.target_countries ?? []);
  // 有沒有改了還沒存（docs/ui-review-2.md D3）
  const dirty =
    nationality !== (initial?.nationality ?? "") ||
    degree !== (initial?.target_degree ?? "master") ||
    major !== (initial?.current_major ?? "") ||
    !sameList(fields, initial?.target_fields ?? []) ||
    !sameList(targets, initial?.target_countries ?? []);
  // 有未存的修改時，重新整理或關掉分頁前，瀏覽器會先問一次。
  // 站內換頁擋不住：react-router 要換成「資料路由」才有 useBlocker，所以在存檔鈕旁邊提醒
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate({
      nationality,
      target_degree: degree,
      current_major: major.trim() || null,
      target_fields: fields,
      target_countries: targets,
    });
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="sr-only">個人資料</CardTitle>
        {/* 送給 AI 的欄位見 ADR-055；畫面上只寫白話，不寫 ADR 編號（docs/ui-review-2.md A3） */}
        <CardDescription>
          只存在這台電腦的資料庫；送給 AI 的只有目前科系與想讀的領域。存檔後，評分會在背景重新計算。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="nationality">國籍（必填）</Label>
            <CountrySelect
              id="nationality"
              options={countries}
              value={nationality ? optionsOf([nationality])[0] : null}
              onChange={(option) => setNationality(option?.code ?? "")}
            />
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
            <Label htmlFor="fields">想讀的領域（選填，可加多個）</Label>
            <TagInput id="fields" value={fields} onChange={setFields} placeholder="打完按 Enter 加一個，例如 Data Science" />
          </div>
          <div className="space-y-1">
            <Label htmlFor="countries">想去的國家（選填，可選多個）</Label>
            <CountryMultiSelect
              id="countries"
              options={countries}
              value={optionsOf(targets)}
              onChange={(options) => setTargets(options.map((option) => option.code))}
            />
          </div>
          {save.isError && (
            <Alert variant="destructive">
              <AlertTitle>沒有存檔</AlertTitle>
              <AlertDescription>{save.error.message}</AlertDescription>
            </Alert>
          )}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? "存檔中…" : "存檔"}
            </Button>
            {dirty ? (
              <span className="text-sm text-muted-foreground">有修改還沒存檔</span>
            ) : (
              save.isSuccess && <span className="text-sm text-muted-foreground">已存檔</span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
