import { Skeleton } from "@/components/ui/skeleton";

// 載入中的畫面：做成和頁面一樣的形狀（標題加幾張卡片），讀者知道接下來會出現什麼（docs/ui-review-2.md A6）
export function PageSkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="載入中">
      <Skeleton className="h-7 w-40" />
      {Array.from({ length: cards }, (_, index) => (
        <div key={index} className="space-y-3 rounded-xl border p-4">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  );
}
