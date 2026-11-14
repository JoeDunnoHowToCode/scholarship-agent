import { useState, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";

// 小標籤輸入框（docs/ui-review-2.md D5）：打完按 Enter 或逗號加一個，按 × 或在空白時按 Backspace 移除。
// 外觀和「想去的國家」的國家選單一樣，同一頁不再有兩種輸入方式
export function TagInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id?: string;
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const items = draft
      .split(/[,，、]/)
      .map((item) => item.trim())
      .filter((item) => item && !value.includes(item));
    if (items.length) onChange([...value, ...items]);
    setDraft("");
  };
  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === "，") {
      event.preventDefault(); // Enter 只用來加標籤，不送出表單
      add();
    } else if (event.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  };
  return (
    <div
      className={cn(
        "flex min-h-9 w-full flex-wrap items-center gap-1 rounded-lg border border-input bg-transparent px-2 py-1 text-sm",
        "focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50",
      )}
    >
      {value.map((item) => (
        <span key={item} className="flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-xs">
          {item}
          <button
            type="button"
            aria-label={`移除${item}`}
            onClick={() => onChange(value.filter((other) => other !== item))}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        onBlur={add} // 打了字沒按 Enter 就去按存檔，也不會漏掉
        placeholder={value.length ? "" : placeholder}
        className="min-w-24 flex-1 bg-transparent px-1 outline-none"
      />
    </div>
  );
}
