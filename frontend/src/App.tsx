import { Menu } from "@base-ui/react/menu";
import { useEffect } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigationType } from "react-router";

import Ask from "@/pages/Ask";
import Logs from "@/pages/Logs";
import Notifications from "@/pages/Notifications";
import Profile from "@/pages/Profile";
import ScholarshipDetail from "@/pages/ScholarshipDetail";
import ScholarshipList from "@/pages/ScholarshipList";
import SettingsPage from "@/pages/Settings";

// 導覽列分主要與次要（ADR-106）：常用的三頁一直看得到；個人資料與管理系統用的頁面收進「更多」選單。
// 原本 7 個項目排一行，手機上每個字被擠成一字一行
const LINKS = [
  { to: "/", label: "獎學金" },
  { to: "/ask", label: "問答" },
  { to: "/notifications", label: "通知" },
];
const MORE_LINKS = [
  { to: "/profile", label: "個人資料" },
  { to: "/logs", label: "紀錄" },
  { to: "/settings", label: "設定" },
];

const linkClass = (active: boolean) =>
  active ? "text-sm font-medium whitespace-nowrap" : "text-sm whitespace-nowrap text-muted-foreground hover:text-foreground";

// 換頁時捲到頁首（UI 計畫 A3）；按上一頁、下一頁（POP）時不動，讓瀏覽器回到原本的位置
function ScrollToTop() {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  useEffect(() => {
    if (navigationType !== "POP") window.scrollTo(0, 0);
  }, [pathname, navigationType]);
  return null;
}

function MoreMenu() {
  const { pathname } = useLocation();
  const current = MORE_LINKS.find((link) => pathname.startsWith(link.to));
  return (
    <Menu.Root>
      {/* 在次要頁面時，按鈕直接寫那一頁的名稱，看得出自己在哪裡 */}
      <Menu.Trigger className={`${linkClass(Boolean(current))} flex cursor-pointer items-center gap-1 rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring`}>
        {current?.label ?? "更多"} <span aria-hidden>▾</span>
      </Menu.Trigger>
      <Menu.Portal>
        <Menu.Positioner sideOffset={8} align="end" className="z-50 outline-none">
          <Menu.Popup className="min-w-32 rounded-lg bg-popover p-1 text-sm text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-none">
            {MORE_LINKS.map((link) => (
              <Menu.LinkItem
                key={link.to}
                closeOnClick
                render={<Link to={link.to} />}
                className="block rounded-md px-3 py-2 outline-none select-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
              >
                {link.label}
              </Menu.LinkItem>
            ))}
          </Menu.Popup>
        </Menu.Positioner>
      </Menu.Portal>
    </Menu.Root>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <ScrollToTop />
      <header className="border-b">
        <nav className="mx-auto flex max-w-5xl items-center gap-5 px-4 py-3 sm:gap-6">
          {/* 品牌名稱回首頁（UI 計畫 D5）；手機上不顯示，和「獎學金」連到同一頁，把位置留給連結 */}
          <NavLink to="/" className="hidden font-semibold whitespace-nowrap sm:inline">
            留學獎學金
          </NavLink>
          {LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === "/"} className={({ isActive }) => linkClass(isActive)}>
              {link.label}
            </NavLink>
          ))}
          <div className="ml-auto">
            <MoreMenu />
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<ScholarshipList />} />
          <Route path="/scholarships/:id" element={<ScholarshipDetail />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
      {/* 時間一律換成台灣時間顯示；在這裡說一次，不在每個時間後面重複（docs/ui-review-2.md A4） */}
      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-muted-foreground">頁面上的時間都是台灣時間。</footer>
    </div>
  );
}
