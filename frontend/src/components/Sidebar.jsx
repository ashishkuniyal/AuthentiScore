// Sidebar.jsx — Main Navigation panel for the SaaS layout
import { 
    Activity, Clock, Search, UploadCloud, Hexagon, LayoutDashboard, 
    FileText, Brain, ShieldAlert, Cpu, Settings, HelpCircle 
} from "lucide-react";

const MENU_GROUPS = [
    {
        title: "Main Menu",
        items: [
            { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
            { id: "scanner",   label: "Scanner",   icon: Search },
            { id: "bulk",      label: "Bulk Analysis", icon: UploadCloud },
            { id: "audit",     label: "Influencer Audit", icon: Activity },
            { id: "history",   label: "Scan History",   icon: Clock },
            { id: "analytics", label: "Analytics", icon: Activity },
            { id: "reports",   label: "Reports", icon: FileText },
        ]
    },
    {
        title: "Intelligence",
        items: [
            { id: "ai-insights", label: "AI Insights", icon: Brain },
            { id: "risk-intel",  label: "Risk Intelligence", icon: ShieldAlert },
            { id: "model-perf",  label: "Model Performance", icon: Cpu },
        ]
    },
    {
        title: "System",
        items: [
            { id: "settings", label: "Settings", icon: Settings },
            { id: "help",     label: "Help & Docs", icon: HelpCircle },
        ]
    }
];

export default function Sidebar({ activeTab, onTabChange }) {
    return (
        <aside
            className="h-screen bg-[var(--bg-app)] border-r border-[var(--border-inner)] flex flex-col sticky top-0 py-6 px-2 md:px-4 shrink-0 z-40 w-[70px] md:w-[260px] transition-all duration-300 overflow-x-hidden"
        >
            {/* Logo Area */}
            <div className="flex items-center gap-3 px-2 mb-6 shrink-0 overflow-hidden">
                <div
                    className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-white shadow-[var(--shadow-glow)]"
                    style={{ background: "linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)" }}
                >
                    <Hexagon size={20} strokeWidth={2.5} />
                </div>
                <div className="hidden md:block">
                    <div className="font-[var(--font-head)] text-lg font-extrabold text-[var(--text-primary)] tracking-[-0.02em] leading-none">
                        AuthentiScore
                    </div>
                    <div className="text-[10px] text-[var(--accent-light)] tracking-[0.08em] uppercase font-bold mt-1">
                        Pro Dashboard
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav 
                className="flex flex-col flex-1 min-h-0 w-full overflow-y-auto overflow-x-hidden custom-scrollbar pb-3 pr-1"
                style={{
                    maskImage: "linear-gradient(to bottom, #000 calc(100% - 28px), transparent)",
                    WebkitMaskImage: "linear-gradient(to bottom, #000 calc(100% - 28px), transparent)",
                }}
            >
                {MENU_GROUPS.map((group, groupIdx) => (
                    <div key={groupIdx} className="mb-4 last:mb-0">
                        <div className="hidden md:block text-[10px] uppercase font-extrabold text-[var(--text-muted)] tracking-[0.1em] px-2 mb-1.5">
                            {group.title}
                        </div>
                        <div className="flex flex-col gap-1">
                            {group.items.map((tab) => {
                                const isActive = activeTab === tab.id;
                                const Icon = tab.icon;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => onTabChange(tab.id)}
                                        className={`flex items-center gap-3 p-2 md:px-3 md:py-2 rounded-xl border text-left w-full transition-all duration-300 justify-center md:justify-start group relative overflow-hidden ${
                                            isActive ? "font-bold shadow-[inset_2px_0_0_var(--nav-active-border)]" 
                                            : "nav-item"
                                        }`}
                                        style={{
                                            backgroundColor: isActive ? 'var(--nav-active-bg)' : undefined,
                                            color: isActive ? 'var(--nav-active-text)' : undefined,
                                            borderColor: isActive ? 'var(--nav-active-bg)' : undefined,
                                        }}
                                    >
                                        {isActive && <div className="absolute left-0 top-0 w-full h-full bg-[linear-gradient(90deg,transparent_0%,var(--bg-surface-secondary)_50%,transparent_100%)] -translate-x-[100%] animate-[shimmer_2s_infinite]" />}
                                        <Icon size={18} color={isActive ? "currentColor" : "currentColor"} className={`shrink-0 transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`} />
                                        <span className="hidden md:block text-sm relative z-10 whitespace-nowrap">{tab.label}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </nav>

            {/* System Status Compact Row */}
            <div className="mt-auto pt-3 border-t border-[var(--border-inner)] shrink-0">
                {/* TODO: Wire latency and statuses to a real system health endpoint */}
                <div 
                    className="p-2.5 rounded-xl flex items-center justify-center md:justify-between border transition-all cursor-default group"
                    style={{ background: 'var(--sys-status-bg)', borderColor: 'var(--sys-status-border)' }}
                    title="ML Engine: 14ms | API Gateway: Online | Database: Connected"
                >
                    <div className="flex items-center gap-2 min-w-0">
                        <span className="w-2 h-2 rounded-full bg-[var(--risk-low)] shadow-[0_0_8px_var(--risk-low)] animate-pulse shrink-0" />
                        <span className="hidden md:inline text-xs font-bold text-[var(--risk-low)] truncate">
                            All systems operational
                        </span>
                    </div>
                    <span className="hidden md:inline text-[11px] text-[var(--text-muted)] font-mono shrink-0 ml-1">
                        14ms
                    </span>
                </div>
            </div>
        </aside>
    );
}
