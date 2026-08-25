import { Link } from "@tanstack/react-router";
import {
  Archive,
  FilePenLine,
  FlaskConical,
  Home,
  Info,
  PanelLeftClose,
  PanelLeft,
  Plus,
} from "lucide-react";
import { useState } from "react";

import { ThemeToggle } from "./ThemeToggle";

const items = [
  { to: "/", label: "Home", icon: Home, exact: true },
  { to: "/hinweise", label: "Hinweise", icon: Info, exact: false },
  { to: "/archiv", label: "Archiv", icon: Archive, exact: false },
  { to: "/neu", label: "Neu hinzufügen", icon: Plus, exact: false },
  { to: "/tenorhilfe", label: "Tenorhilfe", icon: FilePenLine, exact: false },
] as const;

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`sticky top-0 z-40 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 md:flex ${
        collapsed ? "w-[72px]" : "w-[248px]"
      }`}
    >
      <Link
        to="/"
        aria-label="Muc Legal – zum Dashboard"
        className={`flex h-20 items-center ${collapsed ? "justify-center px-3" : "px-4"}`}
      >
        {collapsed ? (
          <span className="grid size-9 shrink-0 place-items-center border border-foreground bg-foreground text-background">
            <span className="text-[11px] font-extrabold uppercase leading-none tracking-[0.06em]">
              MLM
            </span>
          </span>
        ) : (
          <>
            <img
              src="/muclegal-logo.png"
              alt="Muc Legal"
              className="h-16 w-full object-contain object-left dark:hidden"
            />
            <img
              src="/muclegal-logo-dark.png"
              alt=""
              aria-hidden="true"
              className="hidden h-16 w-full object-contain object-left dark:block"
            />
          </>
        )}
      </Link>

      <nav className="flex flex-1 flex-col gap-1 px-3 py-2">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            activeOptions={{ exact: item.exact }}
            title={collapsed ? item.label : undefined}
            className="flex items-center gap-3 rounded-full px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[status=active]:bg-sidebar-accent data-[status=active]:font-medium data-[status=active]:text-sidebar-accent-foreground"
          >
            <item.icon className="size-[18px] shrink-0" strokeWidth={1.75} />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </Link>
        ))}
        <a
          href="/beweis-labor"
          title={collapsed ? "BeweisLab" : undefined}
          className="flex items-center gap-3 rounded-full px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <FlaskConical className="size-[18px] shrink-0" strokeWidth={1.75} />
          {!collapsed && <span className="truncate">BeweisLab</span>}
        </a>
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <ThemeToggle collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? "Seitenleiste ausklappen" : "Seitenleiste einklappen"}
          className="flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          {collapsed ? (
            <PanelLeft className="size-[18px] shrink-0" strokeWidth={1.75} />
          ) : (
            <PanelLeftClose className="size-[18px] shrink-0" strokeWidth={1.75} />
          )}
          {!collapsed && <span>Einklappen</span>}
        </button>
      </div>
    </aside>
  );
}
