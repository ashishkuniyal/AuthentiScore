import { useState, useRef, useEffect } from "react";
import { Bell, Search, User, LogOut, Sun, Moon } from "lucide-react";
import { useAuth } from "../context/useAuth";
import SettingsModal from "./SettingsModal";

export default function Header({ activeTab, notifications = [], onSearch, onNavigate }) {
    const tabName = activeTab.charAt(0).toUpperCase() + activeTab.slice(1);
    const { user, logout } = useAuth();
    const [showUserMenu, setShowUserMenu] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [theme, setTheme] = useState(
        localStorage.getItem("theme") || 
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
    );
    const searchInputRef = useRef(null);

    const unreadCount = notifications.length;

    useEffect(() => {
        const handleKeyDown = (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                searchInputRef.current?.focus();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

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

    return (
        <header
            style={{
                height: 68,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 32px",
                background: "var(--bg-glass-nav)",
                backdropFilter: "blur(20px)",
                WebkitBackdropFilter: "blur(20px)",
                borderBottom: "1px solid var(--border-inner)",
                position: "sticky",
                top: 0,
                zIndex: 1000,
            }}
        >
            {/* Breadcrumbs */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 500, color: "var(--text-secondary)" }}>
                {activeTab !== "dashboard" && (
                    <>
                        <span>Overview</span>
                        <span style={{ color: "var(--border-inner)" }}>/</span>
                    </>
                )}
                <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                    {activeTab === "dashboard" ? "Dashboard Overview" : tabName}
                </span>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                
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
                            padding: "8px 16px 8px 40px",
                            fontSize: 13,
                            color: "var(--text-primary)",
                            outline: "none",
                            width: 280,
                            transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                            boxShadow: "inset 0 2px 4px var(--bg-surface-secondary)"
                        }}
                        onFocus={e => {
                            e.currentTarget.style.borderColor = "var(--accent)";
                            e.currentTarget.style.boxShadow = "0 0 0 2px rgba(99,102,241,0.2), inset 0 2px 4px var(--bg-surface-secondary)";
                            e.currentTarget.style.background = "var(--bg-surface-secondary)";
                            e.currentTarget.style.width = "320px";
                        }}
                        onBlur={e => {
                            e.currentTarget.style.borderColor = "var(--header-search-border)";
                            e.currentTarget.style.boxShadow = "inset 0 2px 4px var(--bg-surface-secondary)";
                            e.currentTarget.style.background = "var(--header-search-bg)";
                            e.currentTarget.style.width = "280px";
                        }}
                    />
                    <div style={{ position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)", display: "flex", gap: 4, pointerEvents: "none" }}>
                        <kbd style={{ background: "var(--bg-surface)", border: "1px solid var(--border-inner)", borderRadius: 4, padding: "2px 6px", fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>Ctrl</kbd>
                        <kbd style={{ background: "var(--bg-surface)", border: "1px solid var(--border-inner)", borderRadius: 4, padding: "2px 6px", fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)", fontWeight: 600 }}>K</kbd>
                    </div>
                </div>

                <div style={{ position: "relative" }}>
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

                <div style={{ position: "relative" }}>
                    <button 
                        onClick={toggleTheme}
                        style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", display: "flex", alignItems: "center" }}
                    >
                        {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
                    </button>
                </div>

                <div style={{ width: 1, height: 24, background: "var(--border-inner)" }} />

                <div style={{ position: "relative" }}>
                    <button 
                        onClick={() => setShowUserMenu(!showUserMenu)}
                        style={{ 
                            display: "flex", alignItems: "center", gap: 10, 
                            background: "var(--btn-secondary-bg)", border: "1px solid var(--btn-secondary-border)", 
                            padding: "6px 14px", borderRadius: 99, cursor: "pointer",
                            transition: "background 0.2s"
                        }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--btn-secondary-hover-bg)"}
                        onMouseLeave={e => e.currentTarget.style.background = "var(--btn-secondary-bg)"}
                    >
                        {user?.avatar ? (
                            <img src={user.avatar} alt="Avatar" style={{ width: 26, height: 26, borderRadius: "50%", objectFit: "cover" }} />
                        ) : (
                            <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}>
                                <User size={14} />
                            </div>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
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
        </header>
    );
}
