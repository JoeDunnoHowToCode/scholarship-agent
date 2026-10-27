import { NavLink, Route, Routes } from "react-router";

import Ask from "@/pages/Ask";
import Notifications from "@/pages/Notifications";
import Profile from "@/pages/Profile";
import ScholarshipDetail from "@/pages/ScholarshipDetail";
import ScholarshipList from "@/pages/ScholarshipList";

const LINKS = [
  { to: "/", label: "獎學金" },
  { to: "/ask", label: "問答" },
  { to: "/profile", label: "個人資料" },
  { to: "/notifications", label: "通知" },
];

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <span className="font-semibold">留學獎學金</span>
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === "/"}
              className={({ isActive }) =>
                isActive ? "text-sm font-medium" : "text-sm text-muted-foreground hover:text-foreground"
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<ScholarshipList />} />
          <Route path="/scholarships/:id" element={<ScholarshipDetail />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/notifications" element={<Notifications />} />
        </Routes>
      </main>
    </div>
  );
}
