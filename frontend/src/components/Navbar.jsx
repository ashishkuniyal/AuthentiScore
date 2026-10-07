// Navbar.jsx — Darker frosted glass on slate background

const TABS = [
    { id: "scanner",   label: "Scanner",   icon: "◎" },
    { id: "bulk",      label: "Bulk Upload", icon: "⎘" },
    { id: "history",   label: "History",   icon: "◷" },
    { id: "analytics", label: "Analytics", icon: "◈" },
];

export default function Navbar({ activeTab, onTabChange }) {
    return (
        <header
            style={{
                position: "sticky",
                top: 0,
                zIndex: 50,
                background: "rgba(15, 23, 42, 0.85)", // Dark slate glass
                backdropFilter: "blur(24px)",
                WebkitBackdropFilter: "blur(24px)",
                borderBottom: "1px solid var(--border-inner)",
                boxShadow: "0 4px 30px rgba(0,0,0,0.15)",
            }}
        >
            <div
                style={{
                    maxWidth: 1280,
                    margin: "0 auto",
                    padding: "0 24px",
                    height: 68,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 24,
                }}
            >
                {/* Logo */}
                <div style={{ display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
                    <div
                        style={{
                            width: 38,
                            height: 38,
                            borderRadius: 12,
                            background: "linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 18,
                            fontWeight: 800,
                            color: "var(--text-primary)",
                            fontFamily: "var(--font-head)",
                            boxShadow: "0 4px 16px rgba(99,102,241,0.4)",
                            border: "1px solid var(--border-hover)",
                        }}
                    >
                        A
                    </div>
                    <div>
                        <div
                            style={{
                                fontFamily: "var(--font-head)",
                                fontWeight: 800,
                                fontSize: 19,
                                color: "var(--text-primary)",
                                letterSpacing: "-0.02em",
                                lineHeight: 1,
                            }}
                        >
                            AuthentiScore
                        </div>
                        <div
                            style={{
                                fontSize: 11,
                                color: "var(--text-muted)",
                                letterSpacing: "0.08em",
                                textTransform: "uppercase",
                                fontWeight: 600,
                                lineHeight: 1,
                                marginTop: 4,
                            }}
                        >
                            AI · ML · NLP
                        </div>
                    </div>
                </div>

                {/* Tab Navigation */}
                <nav
                    style={{
                        display: "flex",
                        gap: 6,
                        background: "var(--border-inner)",
                        border: "1px solid var(--border-inner)",
                        borderRadius: 12,
                        padding: "6px",
                    }}
                >
                    {TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => onTabChange(tab.id)}
                            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                        >
                            <span style={{ marginRight: 6, fontSize: 13, opacity: activeTab === tab.id ? 0.9 : 0.6 }}>{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </nav>

                {/* Status indicator */}
                <div
                    className="hidden sm:flex"
                    style={{
                        alignItems: "center",
                        gap: 8,
                        padding: "6px 14px",
                        borderRadius: 99,
                        background: "rgba(5,150,105,0.15)",
                        border: "1px solid rgba(5,150,105,0.3)",
                        boxShadow: "inset 0 1px 2px var(--border-inner)",
                    }}
                >
                    <span
                        style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: "#34d399",
                            display: "inline-block",
                            animation: "glow-pulse 2s ease infinite",
                            boxShadow: "0 0 8px #34d399",
                        }}
                    />
                    <span style={{ fontSize: 12, fontWeight: 700, color: "#a7f3d0", letterSpacing: "0.02em" }}>
                        Ensemble v2 Online
                    </span>
                </div>
            </div>
        </header>
    );
}
