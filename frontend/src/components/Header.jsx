import { useState, useRef, useEffect, useMemo } from "react";
import { 
    Bell, Search, User, LogOut, Sun, Moon, ArrowLeft,
    Compass, Shield, Layers, History, BarChart3, Settings,
    X, CornerDownLeft
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { getRecentScans } from "../services/api";
import SettingsModal from "./SettingsModal";

export default function Header({ activeTab, notifications = [], onSearch, onNavigate }) {
    const tabName = activeTab.charAt(0).toUpperCase() + activeTab.slice(1);
    const { user, logout } = useAuth();
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [showPalette, setShowPalette] = useState(false);
    const [paletteQuery, setPaletteQuery] = useState("");
    const [recentProfiles, setRecentProfiles] = useState([]);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [searchQuery, setSearchQuery] = useState("");
    const [theme, setTheme] = useState(
        localStorage.getItem("theme") || 
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
    );
    const searchInputRef = useRef(null);
    const paletteInputRef = useRef(null);

    const unreadCount = notifications.length;

    // Ctrl/Cmd + K opens Command Palette
    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setShowPalette(prev => !prev);
            } else if (e.key === 'Escape') {
                setShowPalette(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    // Fetch recent scans when palette opens
    useEffect(() => {
        if (showPalette) {
            setPaletteQuery("");
            setSelectedIndex(0);
            setTimeout(() => paletteInputRef.current?.focus(), 60);
            getRecentScans(8).then(scans => {
                if (Array.isArray(scans)) setRecentProfiles(scans);
            }).catch(() => {});
        }
    }, [showPalette]);

    useEffect(() => {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prev => prev === "dark" ? "light" : "dark");
    };

    const handleSearch = (e) => {
        if (e.key === "Enter" && searchQuery.trim()) {
            if (onSearch) {
                onSearch(searchQuery.trim());
            }
            setSearchQuery(""); // Clear after search
        }
    };

    // Filtered command palette items
    const paletteItems = useMemo(() => {
        const items = [];
        const q = paletteQuery.trim().toLowerCase();

        // 1. Scan Profile Action
        if (q) {
            const cleanHandle = q.replace(/^@/, "");
            items.push({
                id: `scan-${cleanHandle}`,
                type: "action",
                label: `Scan profile: @${cleanHandle}`,
                subtitle: "Run forensic AI detection on this handle",
                icon: Search,
                action: () => {
                    if (onSearch) onSearch(cleanHandle);
                    else if (onNavigate) onNavigate("scanner");
                }
            });
        } else {
            items.push({
                id: "action-new-scan",
                type: "action",
                label: "Run New Scan",
                subtitle: "Launch single account risk scanner",
                icon: Search,
                action: () => onNavigate && onNavigate("scanner")
            });
        }

        // 2. Navigation items
        const navs = [
            { id: "nav-dashboard", label: "Dashboard Overview", subtitle: "Telemetry & KPI command center", icon: Compass, tab: "dashboard" },
            { id: "nav-scanner", label: "Single Scanner", subtitle: "Inspect Instagram, Twitter or TikTok", icon: Shield, tab: "scanner" },
            { id: "nav-bulk", label: "Bulk Scanner", subtitle: "Batch audit multiple handles via CSV", icon: Layers, tab: "bulk" },
            { id: "nav-history", label: "Scan History", subtitle: "Historical profile audit database", icon: History, tab: "history" },
            { id: "nav-analytics", label: "Risk Analytics", subtitle: "Engine component metrics & distribution", icon: BarChart3, tab: "analytics" },
        ];

        navs.forEach(nav => {
            if (!q || nav.label.toLowerCase().includes(q) || nav.subtitle.toLowerCase().includes(q)) {
                items.push({
                    id: nav.id,
                    type: "page",
                    label: nav.label,
                    subtitle: nav.subtitle,
                    icon: nav.icon,
                    action: () => onNavigate && onNavigate(nav.tab)
                });
            }
        });

        // 3. Quick Actions
        const quickActions = [
            {
                id: "action-theme",
                type: "action",
                label: theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode",
                subtitle: "Toggle application theme palette",
                icon: theme === "dark" ? Sun : Moon,
                action: toggleTheme
            },
            {
                id: "action-settings",
                type: "action",
                label: "Open Settings",
                subtitle: "Manage detection sensitivity & API keys",
                icon: Settings,
                action: () => setShowSettingsModal(true)
            }
        ];

        quickActions.forEach(qa => {
            if (!q || qa.label.toLowerCase().includes(q)) {
                items.push(qa);
            }
        });

        // 4. Recent Profiles
        if (recentProfiles.length > 0) {
            recentProfiles.forEach((scan, idx) => {
                const handle = (scan.profile || scan.username || "").replace(/^@/, "");
                const platform = scan.platform || "Instagram";
                if (!handle) return;
                if (!q || handle.toLowerCase().includes(q) || platform.toLowerCase().includes(q)) {
                    items.push({
                        id: `recent-${handle}-${idx}`,
                        type: "profile",
                        label: `@${handle}`,
                        subtitle: `${platform} • ${scan.score || scan.risk_level || "Audit"}`,
                        icon: Shield,
                        action: () => {
                            if (onSearch) onSearch(handle);
                            else if (onNavigate) onNavigate("scanner");
                        }
                    });
                }
            });
        }

        return items;
    }, [paletteQuery, recentProfiles, theme, onNavigate, onSearch]);

    const handlePaletteKeyDown = (e) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setSelectedIndex(prev => (prev + 1) % Math.max(1, paletteItems.length));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setSelectedIndex(prev => (prev - 1 + paletteItems.length) % Math.max(1, paletteItems.length));
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (paletteItems[selectedIndex]) {
                paletteItems[selectedIndex].action();
                setShowPalette(false);
            }
        } else if (e.key === "Escape") {
            e.preventDefault();
            setShowPalette(false);
        }
    };

    return (
        <header
            style={{
                height: 68,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 24px 0 32px",
                gap: 16,
                background: "var(--bg-glass-nav)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                borderBottom: "1px solid var(--border-inner)",
                position: "sticky",
                top: 0,
                zIndex: 1000,
                boxSizing: "border-box",
                width: "100%",
            }}
        >
            {/* Breadcrumbs & Navigation */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, fontWeight: 500 }}>
                {activeTab !== "dashboard" && (
                    <button
                        id="btn-header-back"
                        onClick={() => onNavigate && onNavigate("dashboard")}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 32,
                            height: 32,
                            borderRadius: 8,
                            background: "var(--bg-surface-secondary)",
                            border: "1px solid var(--border-inner)",
                            color: "var(--text-secondary)",
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                        }}
                        className="hover:text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--border-inner)]"
                        title="Back to Dashboard"
                        aria-label="Back to Dashboard"
                    >
                        <ArrowLeft size={16} />
                    </button>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--text-secondary)" }}>
                    {activeTab !== "dashboard" && (
                        <>
                            <button
                                onClick={() => onNavigate && onNavigate("dashboard")}
                                style={{
                                    background: "none",
                                    border: "none",
                                    color: "inherit",
                                    cursor: "pointer",
                                    padding: 0,
                                    fontSize: 14,
                                    fontWeight: 500,
                                }}
                                className="hover:text-[var(--text-primary)] transition-colors"
                            >
                                Overview
                            </button>
                            <span style={{ color: "var(--border-inner)" }}>/</span>
                        </>
                    )}
                    <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                        {activeTab === "dashboard" ? "Dashboard Overview" : tabName}
                    </span>
                </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
                
                {/* Global Search Bar */}
                <div style={{ position: "relative" }} className="hidden sm:block group">
                    <Search size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", zIndex: 2 }} className="transition-colors group-hover:text-[var(--accent-light)]" />
                    <input 
                        ref={searchInputRef}
                        type="text" 
                        placeholder="Search profiles, scans..." 
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={handleSearch}
                        style={{
                            background: "var(--header-search-bg)",
                            border: "1px solid var(--header-search-border)",
                            borderRadius: 12,
                            padding: "8px 84px 8px 40px",
                            fontSize: 13,
                            color: "var(--text-primary)",
                            outline: "none",
                            width: "clamp(200px, 20vw, 280px)",
                            transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                            boxShadow: "inset 0 2px 4px var(--bg-surface-secondary)"
                        }}
                        onFocus={e => {
                            e.currentTarget.style.borderColor = "var(--accent)";
                            e.currentTarget.style.boxShadow = "0 0 0 2px rgba(99,102,241,0.2), inset 0 2px 4px var(--bg-surface-secondary)";
                            e.currentTarget.style.background = "var(--bg-surface-secondary)";
                            e.currentTarget.style.width = "min(320px, 28vw)";
                        }}
                        onBlur={e => {
                            e.currentTarget.style.borderColor = "var(--header-search-border)";
                            e.currentTarget.style.boxShadow = "inset 0 2px 4px var(--bg-surface-secondary)";
                            e.currentTarget.style.background = "var(--header-search-bg)";
                            e.currentTarget.style.width = "clamp(200px, 20vw, 280px)";
                        }}
                    />
                    <div 
                        onClick={() => setShowPalette(true)}
                        style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", display: "flex", gap: 4, cursor: "pointer" }}
                        title="Open Command Palette (Ctrl+K)"
                    >
                        <kbd style={{ background: "var(--bg-surface)", border: "1px solid var(--border-inner)", borderRadius: 4, padding: "2px 6px", fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>Ctrl</kbd>
                        <kbd style={{ background: "var(--bg-surface)", border: "1px solid var(--border-inner)", borderRadius: 4, padding: "2px 6px", fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>K</kbd>
                    </div>
                </div>

                <div style={{ position: "relative", flexShrink: 0 }}>
                    <button 
                        onClick={() => setShowNotifications(!showNotifications)}
                        style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", position: "relative", display: "flex", alignItems: "center" }}
                    >
                        <Bell size={20} />
                        {unreadCount > 0 && (
                            <span style={{ position: "absolute", top: -2, right: -2, width: 8, height: 8, background: "var(--risk-high)", borderRadius: "50%", border: "2px solid var(--bg-surface)", animation: "glow-pulse 2s infinite" }} />
                        )}
                    </button>

                    {showNotifications && (
                        <div className="animate-slide-down" style={{ position: "absolute", top: 32, right: -10, width: 320, background: "var(--bg-card)", border: "1px solid var(--border-inner)", borderRadius: 12, padding: "16px", boxShadow: "var(--shadow-lg)", zIndex: 100 }}>
                            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, borderBottom: "1px solid var(--border-inner)", paddingBottom: 8 }}>Live Notifications</div>
                            {notifications.length === 0 ? (
                                <div style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "12px 0" }}>No recent notifications</div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 300, overflowY: "auto" }}>
                                    {notifications.map((n, i) => (
                                        <div key={i} style={{ fontSize: 13, color: "var(--text-secondary)", background: "var(--bg-surface-secondary)", padding: "10px", borderRadius: 8, borderLeft: "3px solid var(--accent)" }}>
                                            <div style={{ fontWeight: 600, color: "var(--text-primary)" }}>{n.message}</div>
                                            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>Risk: {n.risk_score} • Platform: {n.platform}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <div style={{ position: "relative", flexShrink: 0 }}>
                    <button 
                        onClick={toggleTheme}
                        style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", display: "flex", alignItems: "center" }}
                    >
                        {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
                    </button>
                </div>

                <div style={{ width: 1, height: 24, background: "var(--border-inner)", flexShrink: 0 }} />

                <div style={{ position: "relative", flexShrink: 0 }}>
                    <button 
                        onClick={() => setShowUserMenu(!showUserMenu)}
                        style={{ 
                            display: "flex", alignItems: "center", gap: 9, 
                            background: "var(--btn-secondary-bg)", border: "1px solid var(--btn-secondary-border)", 
                            padding: "6px 14px", borderRadius: 99, cursor: "pointer",
                            transition: "background 0.2s",
                            flexShrink: 0,
                            whiteSpace: "nowrap",
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--btn-secondary-hover-bg)"}
                        onMouseLeave={e => e.currentTarget.style.background = "var(--btn-secondary-bg)"}
                    >
                        {user?.avatar ? (
                            <img src={user.avatar} alt="Avatar" style={{ width: 24, height: 24, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }} />
                        ) : (
                            <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)", flexShrink: 0 }}>
                                <User size={13} />
                            </div>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {user?.firstName && user?.lastName ? `${user.firstName} ${user.lastName}` : (user?.username || "Admin")}
                        </span>
                    </button>

                    {showUserMenu && (
                        <div className="animate-slide-down" style={{ position: "absolute", top: 44, right: 0, width: 260, background: "var(--bg-card)", border: "1px solid var(--border-inner)", borderRadius: 12, padding: "8px", boxShadow: "var(--shadow-lg)", zIndex: 1000 }}>
                            
                            {/* Header Section */}
                            <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px", borderBottom: "1px solid var(--border-inner)", marginBottom: 8 }}>
                                <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--bg-surface)", border: "2px solid var(--border-inner)", overflow: "hidden", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                    {user?.avatar ? <img src={user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <User size={20} color="var(--text-muted)" />}
                                </div>
                                <div style={{ minWidth: 0 }}>
                                    <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                        {user?.firstName && user?.lastName ? `${user.firstName} ${user.lastName}` : (user?.username || "Admin")}
                                    </div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.email}</div>
                                </div>
                            </div>

                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:overview"); }} style={{ display: "block", width: "100%", textAlign: "center", padding: "8px", fontSize: 12, fontWeight: 700, color: "var(--accent)", background: "rgba(99,102,241,0.05)", borderRadius: 6, marginBottom: 8, cursor: "pointer", border: "1px solid rgba(99,102,241,0.1)" }}>
                                View Profile →
                            </button>

                            {/* ACCOUNT */}
                            <div style={{ padding: "0 12px", fontSize: 10, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, marginTop: 12 }}>Account</div>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:profile"); }} className="menu-item">
                                Profile
                            </button>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:preferences"); }} className="menu-item">
                                Preferences
                            </button>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:security"); }} className="menu-item">
                                Security
                            </button>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:notifications"); }} className="menu-item">
                                Notifications
                            </button>

                            {/* WORKSPACE */}
                            <div style={{ padding: "0 12px", fontSize: 10, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, marginTop: 12 }}>Workspace</div>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:team"); }} className="menu-item">
                                Organization & Team
                            </button>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:api-keys"); }} className="menu-item">
                                API Keys
                            </button>

                            {/* BILLING */}
                            <div style={{ padding: "0 12px", fontSize: 10, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, marginTop: 12 }}>Billing</div>
                            <button onClick={() => { setShowUserMenu(false); onNavigate("profile:billing"); }} className="menu-item" style={{ justifyContent: "space-between" }}>
                                <span>Current Plan</span>
                                <span style={{ background: "var(--border-inner)", padding: "2px 6px", borderRadius: 4, fontSize: 10, fontWeight: 800, color: "var(--text-primary)" }}>{user?.plan || "Free"}</span>
                            </button>
                            
                            <div style={{ height: 1, background: "var(--border-inner)", margin: "8px 0" }} />
                            <button 
                                onClick={logout}
                                className="menu-danger-item"
                            >
                                <LogOut size={16} /> Sign out
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Modals */}
            {showSettingsModal && (
                <SettingsModal onClose={() => setShowSettingsModal(false)} />
            )}

            {/* Command Palette Modal (Ctrl/Cmd + K) */}
            {showPalette && (
                <div 
                    className="fixed inset-0 z-[2000] flex items-start justify-center pt-20 px-4 bg-black/60 backdrop-blur-md animate-fade-in"
                    onClick={() => setShowPalette(false)}
                >
                    <div 
                        className="w-full max-w-xl rounded-2xl bg-[var(--bg-card)] border border-[var(--border-inner)] shadow-[var(--shadow-xl)] overflow-hidden flex flex-col animate-scale-in"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Search Input Bar */}
                        <div className="flex items-center px-4 py-3.5 border-b border-[var(--border-inner)] gap-3 bg-[var(--bg-surface-secondary)]">
                            <Search size={18} className="text-[var(--accent-light)] shrink-0" />
                            <input 
                                ref={paletteInputRef}
                                type="text"
                                placeholder="Type a command or search profile handle..."
                                value={paletteQuery}
                                onChange={(e) => {
                                    setPaletteQuery(e.target.value);
                                    setSelectedIndex(0);
                                }}
                                onKeyDown={handlePaletteKeyDown}
                                className="flex-1 bg-transparent border-none outline-none text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] font-medium"
                            />
                            <div className="flex items-center gap-1.5">
                                <kbd className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border-inner)]">ESC</kbd>
                                <button 
                                    onClick={() => setShowPalette(false)}
                                    className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                                    aria-label="Close"
                                >
                                    <X size={15} />
                                </button>
                            </div>
                        </div>

                        {/* Results List */}
                        <div className="max-h-[380px] overflow-y-auto p-2 flex flex-col gap-1 custom-scrollbar">
                            {paletteItems.length === 0 ? (
                                <div className="py-10 text-center text-xs text-[var(--text-muted)]">
                                    No commands or profiles matching &ldquo;{paletteQuery}&rdquo;
                                </div>
                            ) : (
                                paletteItems.map((item, idx) => {
                                    const Icon = item.icon;
                                    const isSelected = idx === selectedIndex;
                                    return (
                                        <div 
                                            key={item.id}
                                            onClick={() => {
                                                item.action();
                                                setShowPalette(false);
                                            }}
                                            onMouseEnter={() => setSelectedIndex(idx)}
                                            className={`flex items-center justify-between p-2.5 rounded-xl cursor-pointer transition-colors ${
                                                isSelected 
                                                    ? "bg-[var(--bg-surface-secondary)] border border-[var(--accent)] text-[var(--text-primary)] shadow-xs" 
                                                    : "hover:bg-[var(--bg-surface-secondary)] border border-transparent text-[var(--text-secondary)]"
                                            }`}
                                        >
                                            <div className="flex items-center gap-3 min-w-0">
                                                <div className={`p-2 rounded-lg border shrink-0 ${isSelected ? "bg-[var(--accent)] text-white border-transparent" : "bg-[var(--bg-card)] border-[var(--border-inner)] text-[var(--text-muted)]"}`}>
                                                    <Icon size={15} />
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="text-xs font-bold text-[var(--text-primary)] truncate">
                                                        {item.label}
                                                    </div>
                                                    {item.subtitle && (
                                                        <div className="text-[10px] text-[var(--text-muted)] truncate">
                                                            {item.subtitle}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            {isSelected && (
                                                <div className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] font-mono shrink-0 ml-2">
                                                    <span>Select</span>
                                                    <CornerDownLeft size={11} />
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            )}
                        </div>

                        {/* Palette Footer */}
                        <div className="flex items-center justify-between px-4 py-2 border-t border-[var(--border-inner)] bg-[var(--bg-surface-secondary)] text-[10px] text-[var(--text-muted)]">
                            <div className="flex items-center gap-3">
                                <span><kbd className="font-mono font-bold">↑↓</kbd> navigate</span>
                                <span><kbd className="font-mono font-bold">↵</kbd> select</span>
                                <span><kbd className="font-mono font-bold">esc</kbd> close</span>
                            </div>
                            <span className="font-bold text-[var(--accent-light)]">AuthentiScore Command Palette</span>
                        </div>
                    </div>
                </div>
            )}
        </header>
    );
}
