"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Network, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { name: "Executions", href: "/", icon: LayoutDashboard },
  { name: "Templates", href: "/templates", icon: Network },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-card-border glass flex flex-col h-screen sticky top-0">
      <div className="p-6">
        <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-emerald-400">
          PrintWave Orchestrator
        </h1>
      </div>
      <nav className="flex-1 px-4 space-y-2 mt-4">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center space-x-3 px-3 py-2.5 rounded-lg transition-all duration-200",
                isActive 
                  ? "bg-primary/20 text-blue-400 border border-primary/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]" 
                  : "text-gray-400 hover:text-gray-100 hover:bg-card-hover"
              )}
            >
              <item.icon className={cn("w-5 h-5", isActive ? "text-blue-400" : "text-gray-500")} />
              <span className="font-medium">{item.name}</span>
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-card-border">
        <div className="flex items-center space-x-3 px-3 py-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></div>
          <span className="text-sm text-gray-400">System Online</span>
        </div>
      </div>
    </aside>
  );
}
