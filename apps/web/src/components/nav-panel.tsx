"use client";

import {
  Bell,
  BookOpenText,
  ChartNoAxesCombined,
  Database,
  FlaskConical,
  LayoutDashboard,
  ListChecks,
  ReceiptText,
  Settings,
  Star
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { label: "总览", href: "/", icon: LayoutDashboard },
  { label: "自选股", href: "/watchlist", icon: Star },
  { label: "组合", href: "/portfolio", icon: ChartNoAxesCombined },
  { label: "预警", href: "/alerts", icon: Bell },
  { label: "研究笔记", href: "/notes", icon: BookOpenText },
  { label: "模拟盘", href: "/paper-trading", icon: ReceiptText },
  { label: "策略实验室", href: "/strategy-lab", icon: FlaskConical },
  { label: "数据导入", href: "/imports", icon: Database },
  { label: "设置", href: "/settings", icon: Settings }
];

export function NavPanel() {
  const pathname = usePathname();
  const selectedItem =
    navItems.find((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href))) ??
    navItems[0];

  return (
    <nav className="left-nav" aria-label="Primary navigation">
      <div className="brand-block">
        <div className="brand-mark">
          <ListChecks size={18} aria-hidden="true" />
        </div>
        <div>
          <h1>VelaQuant</h1>
          <p>星舵智投</p>
        </div>
      </div>

      <div className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = item.label === selectedItem.label;

          return (
            <Link
              aria-current={isActive ? "page" : undefined}
              className={isActive ? "nav-item active" : "nav-item"}
              href={item.href}
              key={item.label}
            >
              <Icon size={17} aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>

      <p className="nav-context">当前模块：{selectedItem.label}</p>
    </nav>
  );
}
