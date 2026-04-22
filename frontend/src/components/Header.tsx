"use client";

import { usePathname } from "next/navigation";
import { Bell, Search } from "lucide-react";

export function Header() {
  const pathname = usePathname();
  
  const getPageTitle = () => {
    if (pathname === "/") return "Executions Dashboard";
    if (pathname === "/templates") return "Template Library";
    if (pathname.startsWith("/executions/")) return "Live Execution Detail";
    return "Dashboard";
  };

  return (
    <header className="h-16 border-b border-card-border glass flex items-center justify-between px-8 sticky top-0 z-10">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">{getPageTitle()}</h2>
      </div>
      
      <div className="flex items-center space-x-6">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500" />
          <input 
            type="text" 
            placeholder="Search executions..." 
            className="bg-card border border-card-border rounded-full pl-10 pr-4 py-1.5 text-sm focus:outline-none focus:border-primary/50 text-gray-200 w-64 placeholder-gray-500"
          />
        </div>
        <button className="relative text-gray-400 hover:text-gray-100 transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-blue-500 rounded-full"></span>
        </button>
      </div>
    </header>
  );
}
