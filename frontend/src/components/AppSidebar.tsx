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

const items = [
  { to: "/", label: "Home", icon: Home, exact: true },
  { to: "/archiv", label: "Archiv", icon: Archive, exact: false },
  { to: "/hinweise", label: "Hinweise", icon: Info, exact: false },
  { to: "/neu", label: "Neu hinzufügen", icon: Plus, exact: false },
  { to: "/tenorhilfe", label: "Tenorschreibhilfe", icon: FilePenLine, exact: false },
] as const;

export function AppSidebar() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`sticky top-0 flex h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-200 ${
        collapsed ? "w-[72px]" : "w-[248px]"
      }`}
    >
      <div className="flex h-16 items-center gap-3 px-4">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          M
        </span>
        {!collapsed && <span className="font-serif text-lg tracking-tight">MucLegal</span>}
      </div>

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
