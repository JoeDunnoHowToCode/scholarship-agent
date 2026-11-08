import { Combobox } from "@base-ui/react/combobox";
import type React from "react";

import { cn } from "@/lib/utils";

// 個人資料頁的國家選單（ADR-091）：可以打中文名稱或國碼搜尋，選項來自後端的完整國家清單
export type CountryOption = { code: string; name: string };

const matches = (item: CountryOption, query: string) => {
  const q = query.trim().toLowerCase();
  return q === "" || item.name.toLowerCase().includes(q) || item.code.toLowerCase() === q;
};

// Enter 是用來選國家的：第一個符合的會自動反白，按 Enter 就選它。
// 擋掉 Enter 往上傳到 <form>，不然沒有反白的選項時，Enter 會直接存檔（實測發生過）
const keepEnterInside = (event: React.KeyboardEvent) => {
  if (event.key === "Enter") event.preventDefault();
};

const fieldClass =
  "flex min-h-9 w-full flex-wrap items-center gap-1 rounded-lg border border-input bg-transparent px-2 py-1 text-sm focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50";

function Popup() {
  return (
    <Combobox.Portal>
      <Combobox.Positioner sideOffset={4} className="z-50 outline-none">
        <Combobox.Popup className="max-h-72 w-(--anchor-width) min-w-56 overflow-y-auto rounded-lg bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10">
          <Combobox.Empty className="px-2 py-1.5 text-muted-foreground empty:hidden">找不到這個國家</Combobox.Empty>
          <Combobox.List>
            {(item: CountryOption) => (
              <Combobox.Item
                key={item.code}
                value={item}
                className="flex cursor-default items-center justify-between gap-2 rounded-md px-2 py-1.5 outline-none select-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
              >
                <span>{item.name}</span>
                <span className="text-xs text-muted-foreground">{item.code}</span>
              </Combobox.Item>
            )}
          </Combobox.List>
        </Combobox.Popup>
      </Combobox.Positioner>
    </Combobox.Portal>
  );
}

// 單選：國籍
export function CountrySelect({
  id,
  options,
  value,
  onChange,
}: {
  id?: string;
  options: CountryOption[];
  value: CountryOption | null;
  onChange: (value: CountryOption | null) => void;
}) {
  return (
    <Combobox.Root
      items={options}
      value={value}
      onValueChange={onChange}
      itemToStringLabel={(item: CountryOption) => item.name}
      isItemEqualToValue={(a: CountryOption, b: CountryOption) => a.code === b.code}
      filter={matches}
      autoHighlight
    >
      <div className={cn(fieldClass, "max-w-64")} onKeyDown={keepEnterInside}>
        <Combobox.Input id={id} placeholder="打中文或國碼搜尋，例如 台灣、TW" className="min-w-0 flex-1 bg-transparent px-1 outline-none" />
      </div>
      <Popup />
    </Combobox.Root>
  );
}

// 多選：想去的國家，選到的用小標籤列出，按 × 移除
export function CountryMultiSelect({
  id,
  options,
  value,
  onChange,
}: {
  id?: string;
  options: CountryOption[];
  value: CountryOption[];
  onChange: (value: CountryOption[]) => void;
}) {
  return (
    <Combobox.Root
      items={options}
      multiple
      value={value}
      onValueChange={onChange}
      itemToStringLabel={(item: CountryOption) => item.name}
      isItemEqualToValue={(a: CountryOption, b: CountryOption) => a.code === b.code}
      filter={matches}
      autoHighlight
    >
      <Combobox.Chips className={fieldClass} onKeyDown={keepEnterInside}>
        <Combobox.Value>
          {(selected: CountryOption[]) =>
            selected.map((item) => (
              <Combobox.Chip key={item.code} className="flex items-center gap-1 rounded-md bg-secondary px-2 py-0.5 text-xs">
                {item.name}
                <Combobox.ChipRemove aria-label={`移除${item.name}`} className="text-muted-foreground hover:text-foreground">
                  ×
                </Combobox.ChipRemove>
              </Combobox.Chip>
            ))
          }
        </Combobox.Value>
        <Combobox.Input id={id} placeholder={value.length ? "" : "打中文或國碼搜尋，可選多個"} className="min-w-24 flex-1 bg-transparent px-1 outline-none" />
      </Combobox.Chips>
      <Popup />
    </Combobox.Root>
  );
}
