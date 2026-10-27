import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { api, unwrap } from "@/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { CYCLE_STATUS_NAMES, nameOf, taipeiTime } from "@/lib/labels";

const ROUTE_NAMES: Record<string, string> = {
  lookup: "查某一筆獎學金",
  filter: "依條件列出",
  semantic: "搜尋原文",
  document: "讀整份文件",
};

export default function Ask() {
  const [question, setQuestion] = useState("");
  const ask = useMutation({
    mutationFn: async (text: string) => unwrap(await api.POST("/api/ask", { body: { question: text } })),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (question.trim()) ask.mutate(question.trim());
  };
  const result = ask.data;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>問答</CardTitle>
          <CardDescription>答案只根據抓下來的資料，附出處；每題約 NT$0–0.3（第 5 天實測），問題會送到 Gemini。</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <Textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="例如：DEAI 要交哪些文件？"
              maxLength={500}
            />
            <Button type="submit" disabled={ask.isPending || !question.trim()}>
              {ask.isPending ? "AI 回答中…" : "送出"}
            </Button>
          </form>
        </CardContent>
      </Card>
      {ask.isError && (
        <Alert variant="destructive">
          <AlertTitle>沒有回答</AlertTitle>
          <AlertDescription>{ask.error.message}</AlertDescription>
        </Alert>
      )}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle>回答</CardTitle>
            <CardDescription>路線：{nameOf(ROUTE_NAMES, result.route)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {result.notes.map((note) => (
              <p key={note} className="text-muted-foreground">
                （{note}）
              </p>
            ))}
            {result.candidates.length > 0 && (
              <p className="text-muted-foreground">
                最像的是：
                {result.candidates.map((c) => (
                  <Link key={c.id} to={`/scholarships/${c.id}`} className="mr-2 hover:underline">
                    {c.name}
                  </Link>
                ))}
              </p>
            )}
            {result.answer && <p className="whitespace-pre-wrap">{result.answer}</p>}
            {result.citations.length > 0 && (
              <div>
                <p className="font-medium">出處</p>
                <ul className="space-y-1">
                  {result.citations.map((c) => (
                    <li key={c.id} className="break-all text-muted-foreground">
                      [{c.id}] <Where where={c.where} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {result.invalid.length > 0 && (
              <p className="text-destructive">答案引用了不存在的編號，已略過：{result.invalid.join("、")}</p>
            )}
            {result.listed.length > 0 && (
              <ul className="space-y-1">
                {result.listed.map((item, index) => (
                  <li key={index}>
                    <Link to={`/scholarships/${item.id}`} className="hover:underline">
                      {item.name}
                    </Link>
                    ｜截止 {taipeiTime(item.closes_at)}（{nameOf(CYCLE_STATUS_NAMES, item.status)}）
                    {item.nationality_unclear && "（國籍待確認）"}
                    {item.deadline_unverified && "（截止日待確認）"}
                    {item.label && `｜${item.label}`}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// 出處是「網址」或「網址 §段落標題」：網址做成連結
function Where({ where }: { where: string }) {
  const [url, ...rest] = where.split(" §");
  if (!url.startsWith("http")) return <>{where}</>;
  return (
    <>
      <a href={url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
        {url}
      </a>
      {rest.length > 0 && ` §${rest.join(" §")}`}
    </>
  );
}
