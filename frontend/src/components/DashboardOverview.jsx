import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { 
    Activity, AlertTriangle, ShieldCheck, ShieldAlert,
    Brain, Clock, RefreshCw, RotateCw, Download, Upload, Search,
    ChevronRight, ChevronUp, ChevronDown, Radio, Layers, SlidersHorizontal,
    X, HelpCircle, GripVertical
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { getDashboardSummary, getRecentScans, getAnalyticsSummary, getModelMetrics } from "../services/api";
import { 
    XAxis, YAxis, Tooltip, ResponsiveContainer, 
    AreaChart, Area, PieChart, Pie, Cell, Line 
} from "recharts";

// ==============================================================
// Constants & Configuration
// ==============================================================

const STORAGE_KEY_V2 = "as_dash_prefs_v2";

const DEFAULT_WIDGETS = [
    { id: "posture", label: "Threat Posture", desc: "Ensemble risk index & gauge", span: 4, icon: ShieldAlert },
    { id: "kpis", label: "KPI Metrics", desc: "Volume, fake rate & model metrics", span: 8, icon: Activity },
    { id: "activity", label: "Scan Activity", desc: "Throughput history & 30-day heatmap", span: 8, icon: Activity },
    { id: "distribution", label: "Risk Distribution", desc: "Donut breakdown of threat tiers", span: 4, icon: ShieldCheck },
    { id: "signals", label: "Risk Signals", desc: "Behavioral, NLP & metadata averages", span: 4, icon: Activity },
    { id: "platform", label: "Platform Mix", desc: "Audits across social networks", span: 4, icon: Layers },
    { id: "watchlist", label: "High-Risk Watchlist", desc: "Surveillance of critical flagged accounts", span: 4, icon: ShieldAlert },
    { id: "recent", label: "Recent Scans", desc: "Collapsible audit feed & rescan actions", span: 8, icon: Clock },
    { id: "insights", label: "AI Security Insights", desc: "Telemetry-driven heuristic findings", span: 4, icon: Brain },
];

const DEFAULT_ORDER = DEFAULT_WIDGETS.map(w => w.id);

const PRESETS = {
    default: {
        id: "default",
        name: "Default",
        desc: "Balanced overview of all telemetry",
        order: DEFAULT_ORDER,
        hidden: [],
        density: "comfortable",
    },
    executive: {
        id: "executive",
        name: "Executive",
        desc: "Posture, high-level KPIs & insights",
        order: ["posture", "kpis", "activity", "insights"],
        hidden: ["distribution", "signals", "platform", "watchlist", "recent"],
        density: "comfortable",
    },
    analyst: {
        id: "analyst",
        name: "Analyst",
        desc: "All 9 widgets in compact data density",
        order: DEFAULT_ORDER,
        hidden: [],
        density: "compact",
    },
    minimal: {
        id: "minimal",
        name: "Minimal",
        desc: "Streamlined KPIs and recent audit feed",
        order: ["kpis", "recent"],
        hidden: ["posture", "activity", "distribution", "signals", "platform", "watchlist", "insights"],
        density: "comfortable",
    },
};

const DEFAULT_PREFS = {
    version: 2,
    preset: "default",
    order: DEFAULT_ORDER,
    hidden: [],
    density: "comfortable", // "comfortable" | "compact"
    defaultRange: "30D",    // "7D" | "30D" | "90D" | "1Y"
    chartMode: "daily",     // "daily" | "cumulative"
    refreshSec: 0,          // 0 = Off, 30, 60, 300
    animations: true,
};

// ==============================================================
// Helper Functions & Formatters
// ==============================================================

const intlNum = new Intl.NumberFormat("en-US");

function formatNumber(num) {
    if (num == null || isNaN(num)) return "—";
    return intlNum.format(num);
}

function parseRiskScore(scoreVal) {
    if (typeof scoreVal === "number" && !isNaN(scoreVal)) {
        return Math.max(0, Math.min(100, Math.round(scoreVal)));
    }
    if (typeof scoreVal === "string") {
        const match = scoreVal.match(/\d+(\.\d+)?/);
        if (match) {
            return Math.max(0, Math.min(100, Math.round(parseFloat(match[0]))));
        }
    }
    return null;
}

function getRiskColor(riskLevel) {
    switch (riskLevel) {
        case "low": return "var(--risk-low)";
        case "medium": return "var(--risk-med)";
        case "high": return "var(--risk-high)";
        case "very_high": return "var(--risk-vhigh)";
        default: return "var(--text-muted)";
    }
}

function getRiskBadgeClass(riskLevel) {
    switch (riskLevel) {
        case "low": return "badge-authentic";
        case "medium": return "badge-suspicious";
        case "high":
        case "very_high": return "badge-fake";
        default: return "badge";
    }
}

function formatRelativeTime(dateInput) {
    if (!dateInput) return "Recently";
    try {
        const date = new Date(dateInput);
        if (isNaN(date.getTime())) return "Recently";
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffSec < 30) return "Just now";
        if (diffSec < 60) return `${diffSec}s ago`;
        if (diffMin < 60) return `${diffMin}m ago`;
        if (diffHour < 24) return `${diffHour}h ago`;
        if (diffDay === 1) return "Yesterday";
        if (diffDay < 7) return `${diffDay}d ago`;
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
        return "Recently";
    }
}

// Cubic ease-out animated number hook (bypassed if animations disabled)
function useCountUp(targetVal, duration = 800, enabled = true) {
    const isSpecial = targetVal == null || targetVal === "—";
    const numeric = typeof targetVal === "number" ? targetVal : parseFloat(targetVal);
    const isValid = !isSpecial && !isNaN(numeric);

    const [count, setCount] = useState(() => (isValid ? 0 : targetVal ?? 0));

    useEffect(() => {
        if (!isValid || !enabled) return;

        let startTs = null;
        let frameId;

        const animate = (timestamp) => {
            if (!startTs) startTs = timestamp;
            const elapsed = timestamp - startTs;
            const progress = Math.min(elapsed / duration, 1);
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const current = easeOut * numeric;

            if (Number.isInteger(numeric)) {
                setCount(Math.round(current));
            } else {
                setCount(Number(current.toFixed(1)));
            }

            if (progress < 1) {
                frameId = requestAnimationFrame(animate);
            }
        };

        frameId = requestAnimationFrame(animate);
        return () => cancelAnimationFrame(frameId);
    }, [isValid, numeric, duration, enabled]);

    if (!enabled) return isValid ? numeric : (targetVal ?? 0);
    return isValid ? count : (targetVal ?? 0);
}

// Load and migrate stored preferences
function loadStoredPrefs() {
    try {
        // One-time migration of legacy "as_dash_hidden"
        let migratedHidden = null;
        const oldHidden = localStorage.getItem("as_dash_hidden");
        if (oldHidden) {
            try {
                migratedHidden = JSON.parse(oldHidden);
            } catch {
                // Ignore parse errors
            }
            try {
                localStorage.removeItem("as_dash_hidden");
            } catch {
                // Ignore
            }
        }

        const raw = localStorage.getItem(STORAGE_KEY_V2);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === "object" && parsed.version === 2) {
                return {
                    ...DEFAULT_PREFS,
                    ...parsed,
                    hidden: Array.isArray(parsed.hidden) ? parsed.hidden : (migratedHidden || []),
                    order: Array.isArray(parsed.order) && parsed.order.length > 0 ? parsed.order : DEFAULT_ORDER,
                };
            }
        }

        if (migratedHidden && Array.isArray(migratedHidden)) {
            const migrated = {
                ...DEFAULT_PREFS,
                hidden: migratedHidden,
                preset: "custom",
            };
            try {
                localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(migrated));
            } catch {
                // Ignore
            }
            return migrated;
        }

        return DEFAULT_PREFS;
    } catch {
        return DEFAULT_PREFS;
    }
}

function detectActivePreset(prefs) {
    for (const [key, p] of Object.entries(PRESETS)) {
        const sameHidden = p.hidden.length === prefs.hidden.length && 
            p.hidden.every(h => prefs.hidden.includes(h));
        const sameDensity = p.density === prefs.density;
        
        // Match order of visible widgets
        const visibleP = p.order.filter(id => !p.hidden.includes(id));
        const visibleCurr = prefs.order.filter(id => !prefs.hidden.includes(id));
        const sameOrder = visibleP.length === visibleCurr.length && 
            visibleP.every((id, idx) => visibleCurr[idx] === id);

        if (sameHidden && sameDensity && sameOrder) {
            return key;
        }
    }
    return "custom";
}

// ==============================================================
// Card Container Components
// ==============================================================

// Professional Card (16px radius, subtle border, no heavy decorative glow)
function BaseCard({ children, className = "", isCompact = false, ...rest }) {
    return (
        <div 
            className={`rounded-2xl border border-[var(--border-inner)] bg-[var(--bg-card)] transition-shadow duration-200 ${
                isCompact ? "p-4" : "p-5 md:p-6"
            } ${className}`}
            {...rest}
        >
            {children}
        </div>
    );
}

// Featured Card with Spotlight and 1px Hairline (Used ONLY on Posture & KPIs)
function FeaturedCard({ children, className = "", isCompact = false, animationsEnabled = true, ...rest }) {
    const handleMouseMove = (e) => {
        if (!animationsEnabled) return;
        const rect = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--mx", `${e.clientX - rect.left}px`);
        e.currentTarget.style.setProperty("--my", `${e.clientY - rect.top}px`);
    };

    return (
        <div 
            onMouseMove={handleMouseMove}
            className={`spotlight-card rounded-2xl border border-[var(--border-inner)] bg-[var(--bg-card)] relative overflow-hidden transition-all duration-200 hover:-translate-y-0.5 ${
                isCompact ? "p-4" : "p-5 md:p-6"
            } ${className}`}
            {...rest}
        >
            {/* Top 1px gradient hairline */}
            <div className="absolute top-0 left-0 right-0 h-[1.5px] bg-gradient-to-r from-[#6366f1] via-[#8b5cf6] to-[#d946ef] opacity-80 pointer-events-none z-20" />
            {children}
        </div>
    );
}

// Standard Section Header
function CardHeader({ title, subtitle, icon: Icon, action }) {
    return (
        <div className="flex justify-between items-start mb-4 relative z-10 gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
                {Icon && (
                    <div className="p-2 bg-[var(--bg-surface-secondary)] rounded-xl border border-[var(--border-inner)] text-[var(--accent-light)] shrink-0 shadow-xs">
                        <Icon size={15} />
                    </div>
                )}
                <div className="min-w-0">
                    <div className="text-[15px] font-semibold text-[var(--text-primary)] tracking-tight truncate">
                        {title}
                    </div>
                    {subtitle && (
                        <div className="text-xs text-[var(--text-muted)] mt-0.5 font-normal truncate">
                            {subtitle}
                        </div>
                    )}
                </div>
            </div>
            {action && <div className="shrink-0">{action}</div>}
        </div>
    );
}

// ==============================================================
// Threat Posture Semicircle Gauge Component
// ==============================================================

function ThreatPostureGauge({ avgRiskScore, fakeCount, scoredTotal, reviewCount, authCount, isCompact, animationsEnabled }) {
    const highRiskPct = scoredTotal > 0 ? (fakeCount / scoredTotal) * 100 : 0;
    const postureRaw = Math.round(100 - (avgRiskScore * 0.4 + highRiskPct * 1.2));
    const targetPosture = scoredTotal === 0 ? 100 : Math.max(0, Math.min(100, isNaN(postureRaw) ? 100 : postureRaw));
    
    const animatedPosture = useCountUp(targetPosture, 800, animationsEnabled);

    // Color and status tiers
    let statusLabel = "Critical";
    let statusColor = "#ef4444";
    if (animatedPosture >= 80) {
        statusLabel = "Secure";
        statusColor = "#10b981";
    } else if (animatedPosture >= 60) {
        statusLabel = "Watch";
        statusColor = "#f59e0b";
    } else if (animatedPosture >= 40) {
        statusLabel = "Elevated";
        statusColor = "#f97316";
    }

    // Semicircle geometry (radius = 85, arc length = PI * 85 ≈ 267.03)
    const arcLength = 267.03;
    const strokeOffset = arcLength * (1 - Math.min(100, Math.max(0, animatedPosture)) / 100);

    const formulaTooltip = `Threat Posture Formula: clamp(round(100 - (avg_risk_score * 0.4 + highRiskPercent * 1.2)), 0, 100)\n• Avg Risk: ${avgRiskScore.toFixed(1)}/100\n• High-Risk Share: ${highRiskPct.toFixed(1)}%\n• Calculated Posture: ${targetPosture}/100`;

    return (
        <FeaturedCard 
            className="flex flex-col justify-between group h-full min-h-[330px]" 
            isCompact={isCompact}
            animationsEnabled={animationsEnabled}
        >
            {/* Header: Single clean status badge (no duplicate label) */}
            <div className="flex justify-between items-start mb-1 relative z-10">
                <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-[var(--bg-surface-secondary)] rounded-xl border border-[var(--border-inner)] text-[var(--accent-light)] shrink-0 shadow-xs">
                        <ShieldAlert size={15} />
                    </div>
                    <div>
                        <div className="text-[15px] font-semibold text-[var(--text-primary)] tracking-tight">
                            Threat Posture
                        </div>
                        <div className="text-xs text-[var(--text-muted)] mt-0.5 font-normal">
                            Ensemble security index
                        </div>
                    </div>
                </div>

                <div 
                    className="px-2.5 py-1 rounded-full text-[11px] font-bold tracking-wide border shadow-xs"
                    style={{ 
                        backgroundColor: `${statusColor}14`, 
                        borderColor: `${statusColor}35`,
                        color: statusColor
                    }}
                >
                    {statusLabel}
                </div>
            </div>

            {/* Semicircle SVG Gauge with threshold tick marks */}
            <div className="relative flex flex-col items-center justify-center my-auto py-1">
                <svg viewBox="0 0 240 135" className="w-52 max-w-full overflow-visible">
                    {/* Background Arc */}
                    <path
                        d="M 35 110 A 85 85 0 0 1 205 110"
                        fill="none"
                        stroke="var(--border-inner)"
                        strokeWidth="13"
                        strokeLinecap="round"
                    />

                    {/* Threshold tick marks at 40, 60, 80 */}
                    {/* 40 threshold */}
                    <line x1="95.9" y1="35.8" x2="91.6" y2="22.5" stroke="var(--border-hover)" strokeWidth="1.5" strokeLinecap="round" />
                    {/* 60 threshold */}
                    <line x1="144.1" y1="35.8" x2="148.4" y2="22.5" stroke="var(--border-hover)" strokeWidth="1.5" strokeLinecap="round" />
                    {/* 80 threshold */}
                    <line x1="183.1" y1="64.1" x2="194.4" y2="55.9" stroke="var(--border-hover)" strokeWidth="1.5" strokeLinecap="round" />

                    {/* Active Value Arc */}
                    <path
                        d="M 35 110 A 85 85 0 0 1 205 110"
                        fill="none"
                        stroke={statusColor}
                        strokeWidth="13"
                        strokeLinecap="round"
                        strokeDasharray={arcLength}
                        strokeDashoffset={strokeOffset}
                        style={{ transition: animationsEnabled ? "stroke-dashoffset 0.8s ease-out, stroke 0.4s ease" : "none" }}
                    />

                    {/* Center Number */}
                    <text
                        x="120"
                        y="88"
                        textAnchor="middle"
                        className="text-4xl font-bold font-mono"
                        fill="var(--text-primary)"
                    >
                        {animatedPosture}
                    </text>

                    {/* High-contrast tick labels */}
                    <text x="35" y="128" textAnchor="middle" className="text-[11px] font-semibold font-mono" fill="var(--text-muted)">
                        0
                    </text>
                    <text x="205" y="128" textAnchor="middle" className="text-[11px] font-semibold font-mono" fill="var(--text-muted)">
                        100
                    </text>
                </svg>

                {/* Single line explanation under gauge with formula tooltip */}
                <p 
                    className="text-xs text-[var(--text-muted)] text-center mt-0.5 cursor-help hover:text-[var(--text-secondary)] transition-colors"
                    title={formulaTooltip}
                >
                    Based on average risk and high-risk rate ⓘ
                </p>
            </div>

            {/* Mini Stats under gauge */}
            <div className="grid grid-cols-3 gap-2 pt-3 border-t border-[var(--border-inner)] relative z-10">
                <div className="flex flex-col items-center p-2 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--risk-high)]">High</span>
                    <span className="text-sm font-bold font-mono text-[var(--text-primary)] mt-0.5 tabular-nums">
                        {formatNumber(fakeCount)}
                    </span>
                </div>
                <div className="flex flex-col items-center p-2 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--risk-med)]">Review</span>
                    <span className="text-sm font-bold font-mono text-[var(--text-primary)] mt-0.5 tabular-nums">
                        {formatNumber(reviewCount)}
                    </span>
                </div>
                <div className="flex flex-col items-center p-2 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--risk-low)]">Clear</span>
                    <span className="text-sm font-bold font-mono text-[var(--text-primary)] mt-0.5 tabular-nums">
                        {formatNumber(authCount)}
                    </span>
                </div>
            </div>
        </FeaturedCard>
    );
}

// ==============================================================
// Consistent Anatomy KPI Card
// ==============================================================

function KpiCard({ 
    label, 
    numericValue,
    displaySuffix = "",
    deltaText, 
    deltaFootnote,
    progressVal, 
    progressColor, 
    footnote, 
    icon: Icon, 
    type, 
    sparklineData, 
    isTotalCard = false,
    isCompact = false,
    animationsEnabled = true
}) {
    const animatedNumber = useCountUp(numericValue, 750, animationsEnabled);
    const hasNumeric = numericValue != null && !isNaN(numericValue);
    const finalDisplay = hasNumeric 
        ? `${formatNumber(animatedNumber)}${displaySuffix}` 
        : "—";

    return (
        <FeaturedCard 
            className="flex flex-col justify-between group rounded-2xl relative min-h-[155px]"
            isCompact={isCompact}
            animationsEnabled={animationsEnabled}
        >
            <div>
                <div className="flex justify-between items-start relative z-10 mb-2">
                    <div className="flex flex-col gap-1 min-w-0">
                        <span className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] truncate">
                            {label}
                        </span>
                        <span className="text-3xl font-bold font-mono tracking-tight text-[var(--text-primary)] tabular-nums">
                            {finalDisplay}
                        </span>
                    </div>
                    <div 
                        style={{ backgroundColor: `var(--kpi-${type}-bg)`, color: `var(--kpi-${type}-icon)` }} 
                        className="p-2.5 rounded-xl border border-[var(--border-inner)] transition-transform duration-200 group-hover:scale-105 shadow-xs shrink-0"
                    >
                        <Icon size={18} />
                    </div>
                </div>

                {/* Consistent share progress bar for fake/auth/accuracy */}
                {progressVal !== undefined && (
                    <div className="w-full bg-[var(--border-inner)] h-1.5 rounded-full overflow-hidden my-2.5 relative z-10">
                        <div 
                            className="h-full rounded-full transition-all duration-500 ease-out" 
                            style={{ 
                                width: `${Math.min(100, Math.max(0, progressVal))}%`, 
                                backgroundColor: progressColor || `var(--kpi-${type}-icon)` 
                            }} 
                        />
                    </div>
                )}
            </div>

            {/* Consistent height footer on all 4 cards */}
            <div className="flex items-end justify-between mt-2 pt-2 border-t border-[var(--border-inner)] relative z-10 h-7">
                <div className="flex items-center gap-1.5 text-xs font-medium truncate w-full">
                    {deltaText && (
                        <span className="text-[var(--accent-light)] font-mono font-semibold shrink-0">
                            {deltaText}
                        </span>
                    )}

                    {deltaFootnote && (
                        <span className="text-[var(--text-muted)] text-[11px] truncate">
                            {deltaFootnote}
                        </span>
                    )}

                    {footnote && (
                        <span 
                            className="text-[var(--text-muted)] text-[11px] truncate cursor-help"
                            title={footnote}
                        >
                            {footnote}
                        </span>
                    )}
                </div>
            </div>

            {/* Total Scans full-width bottom sparkline */}
            {isTotalCard && sparklineData && sparklineData.length > 0 && (
                <div className="absolute bottom-0 left-0 right-0 h-10 overflow-hidden pointer-events-none opacity-40 group-hover:opacity-70 transition-opacity z-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={sparklineData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="totalSparkGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="var(--kpi-total-icon)" stopOpacity={0.4} />
                                    <stop offset="100%" stopColor="var(--kpi-total-icon)" stopOpacity={0.0} />
                                </linearGradient>
                            </defs>
                            <Area 
                                type="monotone" 
                                dataKey="value" 
                                stroke="var(--kpi-total-icon)" 
                                strokeWidth={2} 
                                fill="url(#totalSparkGrad)" 
                                isAnimationActive={false} 
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            )}
        </FeaturedCard>
    );
}

// ==============================================================
// Slide-Over Customize Drawer (React Portal to document.body)
// ==============================================================

function CustomizeDrawer({ 
    isOpen, 
    onClose, 
    prefs, 
    setPrefs, 
    onReset 
}) {
    const drawerRef = useRef(null);
    const [draggedId, setDraggedId] = useState(null);
    const [dropTargetId, setDropTargetId] = useState(null);
    const [confirmReset, setConfirmReset] = useState(false);

    const handleClose = useCallback(() => {
        setConfirmReset(false);
        onClose();
    }, [onClose]);

    // Focus trap and Esc key handler
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e) => {
            if (e.key === "Escape") {
                e.preventDefault();
                handleClose();
                return;
            }

            if (e.key === "Tab") {
                const drawerEl = drawerRef.current;
                if (!drawerEl) return;
                const focusables = Array.from(
                    drawerEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"]), [role="switch"]')
                ).filter(el => !el.disabled && el.offsetParent !== null);

                if (focusables.length === 0) return;
                const first = focusables[0];
                const last = focusables[focusables.length - 1];

                if (e.shiftKey) {
                    if (document.activeElement === first) {
                        e.preventDefault();
                        last.focus();
                    }
                } else {
                    if (document.activeElement === last) {
                        e.preventDefault();
                        first.focus();
                    }
                }
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, handleClose]);

    if (!isOpen) return null;

    const activePresetKey = detectActivePreset(prefs);

    const handleApplyPreset = (presetKey) => {
        const p = PRESETS[presetKey];
        if (!p) return;
        setPrefs(prev => ({
            ...prev,
            preset: presetKey,
            order: [...p.order],
            hidden: [...p.hidden],
            density: p.density,
        }));
    };

    const toggleWidget = (id) => {
        setPrefs(prev => {
            const nextHidden = prev.hidden.includes(id)
                ? prev.hidden.filter(w => w !== id)
                : [...prev.hidden, id];
            return {
                ...prev,
                hidden: nextHidden,
                preset: "custom",
            };
        });
    };

    const moveWidget = (id, direction) => {
        setPrefs(prev => {
            const order = [...prev.order];
            const idx = order.indexOf(id);
            if (idx === -1) return prev;
            const targetIdx = direction === "up" ? idx - 1 : idx + 1;
            if (targetIdx < 0 || targetIdx >= order.length) return prev;

            const temp = order[idx];
            order[idx] = order[targetIdx];
            order[targetIdx] = temp;

            return {
                ...prev,
                order,
                preset: "custom",
            };
        });
    };

    const handleDragStart = (e, id) => {
        e.dataTransfer.setData("text/plain", id);
        setDraggedId(id);
    };

    const handleDrop = (e, targetId) => {
        e.preventDefault();
        const sourceId = e.dataTransfer.getData("text/plain") || draggedId;
        if (!sourceId || sourceId === targetId) return;

        setPrefs(prev => {
            const order = [...prev.order];
            const srcIdx = order.indexOf(sourceId);
            const tgtIdx = order.indexOf(targetId);
            if (srcIdx === -1 || tgtIdx === -1) return prev;

            order.splice(srcIdx, 1);
            order.splice(tgtIdx, 0, sourceId);

            return {
                ...prev,
                order,
                preset: "custom",
            };
        });
        setDraggedId(null);
        setDropTargetId(null);
    };

    return createPortal(
        <div 
            className="fixed inset-0 z-[9999] flex justify-end"
            role="dialog" 
            aria-modal="true" 
            aria-labelledby="customize-drawer-title"
        >
            {/* Dimmed backdrop */}
            <div 
                className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity duration-200"
                onClick={handleClose}
                aria-hidden="true"
            />

            {/* Slide-over Drawer / Bottom-sheet on mobile */}
            <div 
                ref={drawerRef}
                className="relative z-10 w-full sm:max-w-[420px] bg-[var(--bg-card)] border-l border-[var(--border-inner)] shadow-[var(--shadow-lg)] flex flex-col h-full max-sm:h-[88vh] max-sm:bottom-0 max-sm:rounded-t-2xl max-sm:border-t animate-slide-down sm:animate-fade-in"
            >
                {/* Drawer Header */}
                <div className="flex items-start justify-between p-5 border-b border-[var(--border-inner)] shrink-0">
                    <div>
                        <div className="flex items-center gap-2">
                            <h2 id="customize-drawer-title" className="text-lg font-bold text-[var(--text-primary)] tracking-tight">
                                Customize dashboard
                            </h2>
                            {activePresetKey === "custom" && (
                                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-[var(--accent)] text-white">
                                    Custom
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                            Changes apply instantly and are saved to this browser.
                        </p>
                    </div>
                    <button 
                        onClick={handleClose}
                        className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-secondary)] transition-colors cursor-pointer"
                        aria-label="Close customize drawer"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Drawer Scrollable Body */}
                <div className="flex-1 overflow-y-auto p-5 space-y-6">
                    
                    {/* Section 1: Presets */}
                    <div>
                        <div className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-3">
                            Presets
                        </div>
                        <div className="grid grid-cols-2 gap-2.5">
                            {Object.entries(PRESETS).map(([key, p]) => {
                                const isSelected = activePresetKey === key;
                                return (
                                    <button
                                        key={key}
                                        onClick={() => handleApplyPreset(key)}
                                        className={`flex flex-col text-left p-3 rounded-xl border transition-all cursor-pointer ${
                                            isSelected 
                                                ? "border-[var(--accent)] bg-[var(--bg-surface-secondary)] shadow-xs" 
                                                : "border-[var(--border-inner)] hover:border-[var(--border-hover)] bg-[var(--bg-card)]"
                                        }`}
                                    >
                                        <div className="flex items-center justify-between mb-1.5">
                                            <span className="text-xs font-bold text-[var(--text-primary)]">
                                                {p.name}
                                            </span>
                                            {isSelected && (
                                                <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                                            )}
                                        </div>
                                        <span className="text-[11px] text-[var(--text-muted)] line-clamp-2">
                                            {p.desc}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Section 2: Widgets Reordering & Toggles */}
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                                Widgets ({DEFAULT_WIDGETS.length - prefs.hidden.length} active)
                            </span>
                            <span className="text-[11px] text-[var(--text-muted)]">
                                Drag or use arrows
                            </span>
                        </div>

                        <div className="space-y-2">
                            {prefs.order.map((id, index) => {
                                const widget = DEFAULT_WIDGETS.find(w => w.id === id);
                                if (!widget) return null;
                                const isVisible = !prefs.hidden.includes(id);
                                const Icon = widget.icon;
                                const isDragging = draggedId === id;
                                const isDropTarget = dropTargetId === id;

                                return (
                                    <div
                                        key={id}
                                        draggable
                                        onDragStart={(e) => handleDragStart(e, id)}
                                        onDragOver={(e) => { e.preventDefault(); setDropTargetId(id); }}
                                        onDragLeave={() => { if (dropTargetId === id) setDropTargetId(null); }}
                                        onDrop={(e) => handleDrop(e, id)}
                                        onDragEnd={() => { setDraggedId(null); setDropTargetId(null); }}
                                        className={`flex items-center justify-between p-2.5 rounded-xl border transition-all ${
                                            isDragging ? "opacity-40" : "opacity-100"
                                        } ${
                                            isDropTarget ? "border-[var(--accent)] bg-[var(--bg-surface-secondary)]" : "border-[var(--border-inner)] bg-[var(--bg-card)]"
                                        }`}
                                    >
                                        {/* Drag Handle & Info */}
                                        <div className="flex items-center gap-2.5 min-w-0">
                                            <div className="cursor-grab active:cursor-grabbing text-[var(--text-muted)] hover:text-[var(--text-primary)] p-0.5">
                                                <GripVertical size={14} />
                                            </div>
                                            <div className="flex items-center gap-2 min-w-0">
                                                <div className="p-1 rounded bg-[var(--bg-surface-secondary)] text-[var(--accent-light)] shrink-0">
                                                    <Icon size={13} />
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="text-xs font-semibold text-[var(--text-primary)] truncate">
                                                        {widget.label}
                                                    </div>
                                                    <div className="text-[10px] text-[var(--text-muted)] truncate">
                                                        {widget.desc}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Actions: Reorder Buttons + Accessible Switch */}
                                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                                            <button 
                                                disabled={index === 0}
                                                onClick={() => moveWidget(id, "up")}
                                                className="p-1 rounded hover:bg-[var(--bg-surface-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 cursor-pointer"
                                                title="Move up"
                                                aria-label={`Move ${widget.label} up`}
                                            >
                                                <ChevronUp size={13} />
                                            </button>
                                            <button 
                                                disabled={index === prefs.order.length - 1}
                                                onClick={() => moveWidget(id, "down")}
                                                className="p-1 rounded hover:bg-[var(--bg-surface-secondary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 cursor-pointer"
                                                title="Move down"
                                                aria-label={`Move ${widget.label} down`}
                                            >
                                                <ChevronDown size={13} />
                                            </button>

                                            {/* Proper Toggle Switch (not native checkbox) */}
                                            <button
                                                role="switch"
                                                aria-checked={isVisible}
                                                onClick={() => toggleWidget(id)}
                                                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-1 ${
                                                    isVisible ? "bg-[var(--accent)]" : "bg-[var(--border-hover)]"
                                                }`}
                                                aria-label={`Toggle ${widget.label}`}
                                            >
                                                <span 
                                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs transition duration-200 ease-in-out my-auto ml-0.5 ${
                                                        isVisible ? "translate-x-4" : "translate-x-0"
                                                    }`} 
                                                />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Section 3: Display Settings */}
                    <div className="space-y-4 pt-2 border-t border-[var(--border-inner)]">
                        <div className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                            Display preferences
                        </div>

                        {/* Density */}
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xs font-semibold text-[var(--text-primary)]">Layout density</div>
                                <div className="text-[11px] text-[var(--text-muted)]">Spacing and card padding</div>
                            </div>
                            <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                {["comfortable", "compact"].map(d => (
                                    <button
                                        key={d}
                                        onClick={() => setPrefs(prev => ({ ...prev, density: d, preset: "custom" }))}
                                        className={`px-2.5 py-1 text-xs font-bold rounded-lg transition-all capitalize cursor-pointer ${
                                            prefs.density === d 
                                                ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs" 
                                                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                        }`}
                                    >
                                        {d}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Default Range */}
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xs font-semibold text-[var(--text-primary)]">Default time range</div>
                                <div className="text-[11px] text-[var(--text-muted)]">Initial filter window</div>
                            </div>
                            <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                {["7D", "30D", "90D", "1Y"].map(r => (
                                    <button
                                        key={r}
                                        onClick={() => setPrefs(prev => ({ ...prev, defaultRange: r }))}
                                        className={`px-2 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                            prefs.defaultRange === r 
                                                ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs" 
                                                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                        }`}
                                    >
                                        {r}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Default Chart Mode */}
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xs font-semibold text-[var(--text-primary)]">Activity chart mode</div>
                                <div className="text-[11px] text-[var(--text-muted)]">Daily vs total throughput</div>
                            </div>
                            <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                {[
                                    { id: "daily", label: "Daily" },
                                    { id: "cumulative", label: "Total" }
                                ].map(m => (
                                    <button
                                        key={m.id}
                                        onClick={() => setPrefs(prev => ({ ...prev, chartMode: m.id }))}
                                        className={`px-2.5 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                            prefs.chartMode === m.id 
                                                ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs" 
                                                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                        }`}
                                    >
                                        {m.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Auto-Refresh Interval */}
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xs font-semibold text-[var(--text-primary)]">Auto-refresh</div>
                                <div className="text-[11px] text-[var(--text-muted)]">Telemetry polling cadence</div>
                            </div>
                            <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                {[
                                    { sec: 0, label: "Off" },
                                    { sec: 30, label: "30s" },
                                    { sec: 60, label: "60s" },
                                    { sec: 300, label: "5m" },
                                ].map(opt => (
                                    <button
                                        key={opt.sec}
                                        onClick={() => setPrefs(prev => ({ ...prev, refreshSec: opt.sec }))}
                                        className={`px-2 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                            prefs.refreshSec === opt.sec 
                                                ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs" 
                                                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                        }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Animations Toggle */}
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xs font-semibold text-[var(--text-primary)]">Animations & spotlight</div>
                                <div className="text-[11px] text-[var(--text-muted)]">Count-up effects and card tracking</div>
                            </div>
                            <button
                                role="switch"
                                aria-checked={prefs.animations}
                                onClick={() => setPrefs(prev => ({ ...prev, animations: !prev.animations }))}
                                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-1 ${
                                    prefs.animations ? "bg-[var(--accent)]" : "bg-[var(--border-hover)]"
                                }`}
                                aria-label="Toggle animations"
                            >
                                <span 
                                    className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs transition duration-200 ease-in-out my-auto ml-0.5 ${
                                        prefs.animations ? "translate-x-4" : "translate-x-0"
                                    }`} 
                                />
                            </button>
                        </div>

                    </div>

                </div>

                {/* Sticky Drawer Footer with Reset Confirmation */}
                <div className="p-4 border-t border-[var(--border-inner)] bg-[var(--bg-card)] shrink-0 flex items-center justify-between gap-3">
                    {confirmReset ? (
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-[var(--risk-high)] font-semibold">Confirm?</span>
                            <button
                                onClick={() => { onReset(); setConfirmReset(false); }}
                                className="px-2.5 py-1.5 text-xs font-bold rounded-lg bg-[rgba(239,68,68,0.12)] text-[var(--risk-high)] border border-[rgba(239,68,68,0.3)] hover:bg-[rgba(239,68,68,0.2)] cursor-pointer"
                            >
                                Yes, reset
                            </button>
                            <button
                                onClick={() => setConfirmReset(false)}
                                className="px-2 py-1.5 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                            >
                                Cancel
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => setConfirmReset(true)}
                            className="px-3 py-2 text-xs font-semibold rounded-xl text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-secondary)] transition-colors cursor-pointer"
                        >
                            Reset to default
                        </button>
                    )}

                    <button
                        onClick={handleClose}
                        className="px-5 py-2 text-xs font-bold rounded-xl bg-[var(--btn-primary-bg)] text-white shadow-xs hover:opacity-95 transition-opacity cursor-pointer ml-auto"
                    >
                        Done
                    </button>
                </div>

            </div>
        </div>,
        document.body
    );
}

// ==============================================================
// Keyboard Shortcuts Help Popover
// ==============================================================

function ShortcutsPopover({ isOpen, onClose }) {
    if (!isOpen) return null;

    const shortcuts = [
        { key: "R", desc: "Refresh telemetry data" },
        { key: "N", desc: "New profile scan" },
        { key: "B", desc: "Bulk CSV scanner" },
        { key: "E", desc: "Export recent scans CSV" },
        { key: "L", desc: "Toggle live auto-refresh" },
        { key: "C", desc: "Customize dashboard layout" },
        { key: "?", desc: "Toggle keyboard shortcuts help" },
        { key: "Esc", desc: "Close drawer or popover" },
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50 backdrop-blur-xs" onClick={onClose} />
            <div className="relative z-10 w-full max-w-sm rounded-2xl bg-[var(--bg-card)] border border-[var(--border-inner)] p-5 shadow-[var(--shadow-lg)] animate-scale-in">
                <div className="flex justify-between items-center pb-3 border-b border-[var(--border-inner)] mb-4">
                    <div className="flex items-center gap-2">
                        <HelpCircle size={16} className="text-[var(--accent-light)]" />
                        <span className="text-sm font-bold text-[var(--text-primary)]">Keyboard shortcuts</span>
                    </div>
                    <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer">
                        <X size={16} />
                    </button>
                </div>
                <div className="space-y-2.5">
                    {shortcuts.map(s => (
                        <div key={s.key} className="flex items-center justify-between text-xs">
                            <span className="text-[var(--text-secondary)]">{s.desc}</span>
                            <kbd className="px-2 py-0.5 rounded bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] font-mono font-bold text-[11px] text-[var(--text-primary)]">
                                {s.key}
                            </kbd>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// ==============================================================
// Main Dashboard Overview Component
// ==============================================================

export default function DashboardOverview({ onNavigate, onSearch }) {
    const { user } = useAuth();
    
    // Core Data States
    const [summary, setSummary] = useState(null);
    const [recentScans, setRecentScans] = useState([]);
    const [analytics, setAnalytics] = useState(null);
    const [modelMetrics, setModelMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    
    // Preferences (Config-Driven & Versioned)
    const [prefs, setPrefs] = useState(() => loadStoredPrefs());

    // Save preferences to localStorage whenever changed
    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY_V2, JSON.stringify(prefs));
        } catch (e) {
            console.error("Failed to persist dashboard preferences", e);
        }
    }, [prefs]);

    // View States driven by global preferences / controls
    const [timeRange, setTimeRange] = useState(() => prefs.defaultRange || "30D");
    const activityChartMode = prefs.chartMode || "daily";
    const setActivityChartMode = (mode) => setPrefs(prev => ({ ...prev, chartMode: mode }));
    const [filterRisk, setFilterRisk] = useState("all");
    const [scanSearchQuery, setScanSearchQuery] = useState("");
    const [isLive, setIsLive] = useState(() => prefs.refreshSec > 0);
    const [lastUpdated, setLastUpdated] = useState(new Date());
    const [timeAgoText, setTimeAgoText] = useState("Just now");
    
    // Modal states
    const [showCustomize, setShowCustomize] = useState(false);
    const [showShortcuts, setShowShortcuts] = useState(false);
    const customizeBtnRef = useRef(null);

    // ----------------------------------------------------------
    // Data Loading with Promise.allSettled
    // ----------------------------------------------------------
    const loadDashboardData = useCallback(async () => {
        setLoading(true);
        setError("");
        try {
            const days = timeRange === "7D" ? 7 : timeRange === "30D" ? 30 : timeRange === "90D" ? 90 : 365;
            const results = await Promise.allSettled([
                getDashboardSummary(),
                getRecentScans(30),
                getAnalyticsSummary(days),
                getModelMetrics()
            ]);

            let failureCount = 0;
            if (results[0].status === "fulfilled") setSummary(results[0].value); else failureCount++;
            if (results[1].status === "fulfilled") setRecentScans(results[1].value); else failureCount++;
            if (results[2].status === "fulfilled") setAnalytics(results[2].value); else failureCount++;
            if (results[3].status === "fulfilled") setModelMetrics(results[3].value); else failureCount++;

            if (failureCount === 4) {
                setError("Unable to connect to AuthentiScore API services. Please verify backend is running.");
            }
            setLastUpdated(new Date());
            setTimeAgoText("Just now");
        } catch (err) {
            setError(err.message || "Failed to load dashboard data");
        } finally {
            setLoading(false);
        }
    }, [timeRange]);

    useEffect(() => {
        loadDashboardData();
    }, [loadDashboardData]);

    // Live Auto-Refresh Cadence
    useEffect(() => {
        if (!isLive) return;
        const intervalMs = (prefs.refreshSec > 0 ? prefs.refreshSec : 60) * 1000;
        const interval = setInterval(() => {
            loadDashboardData();
        }, intervalMs);
        return () => clearInterval(interval);
    }, [isLive, prefs.refreshSec, loadDashboardData]);

    // Elapsed Time Ticker
    useEffect(() => {
        const ticker = setInterval(() => {
            const now = new Date();
            const sec = Math.floor((now - lastUpdated) / 1000);
            if (sec < 30) {
                setTimeAgoText("Just now");
            } else if (sec < 60) {
                setTimeAgoText(`${sec}s ago`);
            } else {
                const min = Math.floor(sec / 60);
                setTimeAgoText(`${min}m ago`);
            }
        }, 10000);
        return () => clearInterval(ticker);
    }, [lastUpdated]);

    // ----------------------------------------------------------
    // Export Report Handler (Client-side CSV generator)
    // ----------------------------------------------------------
    const handleExportReport = useCallback(() => {
        if (!recentScans || recentScans.length === 0) {
            alert("No recent scans available to export.");
            return;
        }
        const headers = ["Profile", "Platform", "Score", "Status", "Date"];
        const rows = recentScans.map(s => [
            `"${(s.profile || s.username || "unknown").replace(/"/g, '""')}"`,
            `"${(s.platform || "unknown").replace(/"/g, '""')}"`,
            `"${(s.score || "N/A").replace(/"/g, '""')}"`,
            `"${(s.status || "N/A").replace(/"/g, '""')}"`,
            `"${(s.date || "").replace(/"/g, '""')}"`
        ]);

        const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `authentiscore_scans_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }, [recentScans]);

    // ----------------------------------------------------------
    // Global Keyboard Shortcuts (R, N, B, E, L, C, ?)
    // ----------------------------------------------------------
    useEffect(() => {
        const handleKeyDown = (e) => {
            const tag = e.target?.tagName?.toLowerCase();
            if (tag === "input" || tag === "textarea" || tag === "select" || e.target?.isContentEditable) {
                return;
            }
            if (e.ctrlKey || e.metaKey || e.altKey) {
                return;
            }

            const key = e.key.toLowerCase();
            if (key === "r") {
                e.preventDefault();
                loadDashboardData();
            } else if (key === "n") {
                e.preventDefault();
                if (onNavigate) onNavigate("scanner");
            } else if (key === "b") {
                e.preventDefault();
                if (onNavigate) onNavigate("bulk");
            } else if (key === "e") {
                e.preventDefault();
                handleExportReport();
            } else if (key === "l") {
                e.preventDefault();
                setIsLive(prev => !prev);
            } else if (key === "c") {
                e.preventDefault();
                setShowCustomize(prev => !prev);
            } else if (key === "?") {
                e.preventDefault();
                setShowShortcuts(prev => !prev);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [loadDashboardData, onNavigate, handleExportReport]);

    // ----------------------------------------------------------
    // Computed Data & Single Source of Truth
    // ----------------------------------------------------------
    const greeting = useMemo(() => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 17) return "Good afternoon";
        return "Good evening";
    }, []);

    const userName = user?.firstName || user?.full_name?.split(" ")[0] || "Security Lead";

    const rangeLabel = useMemo(() => {
        switch (timeRange) {
            case "7D": return "7 days";
            case "30D": return "30 days";
            case "90D": return "90 days";
            case "1Y": return "year";
            default: return "30 days";
        }
    }, [timeRange]);

    // Single source of truth: analytics.classification_counts
    const counts = analytics?.classification_counts;
    const hasCounts = Boolean(counts);

    const fakeProfilesCount = hasCounts
        ? ((counts.high || 0) + (counts.very_high || 0))
        : (summary?.fake_profiles ?? 0);

    const reviewCount = hasCounts ? (counts.medium || 0) : 0;

    const authenticProfilesCount = hasCounts
        ? (counts.low || 0)
        : (summary?.authentic_profiles ?? 0);

    const insufficientCount = hasCounts
        ? (counts.insufficient_data || 0)
        : (summary?.insufficient_data ?? 0);

    const scoredTotal = fakeProfilesCount + reviewCount + authenticProfilesCount;
    const totalScans = analytics?.total_scans ?? summary?.total_scans ?? 0;
    const avgRiskScore = analytics?.average_risk_score ?? 0;

    // Compressed Hero Summary Sentence
    const heroSummaryText = useMemo(() => {
        if (totalScans === 0) {
            return "No audit logs recorded yet. Begin your first single or bulk scan to analyze profile authenticity.";
        }
        const reviewNote = reviewCount > 0 ? ` (${formatNumber(reviewCount)} need manual review)` : "";
        return `Your ensemble engines evaluated ${formatNumber(totalScans)} profile${totalScans === 1 ? "" : "s"} over the last ${rangeLabel}, detecting ${formatNumber(fakeProfilesCount)} high-risk threat${fakeProfilesCount === 1 ? "" : "s"}${reviewNote}.`;
    }, [totalScans, rangeLabel, fakeProfilesCount, reviewCount]);

    // Posture status for the status banner
    const highRiskPct = scoredTotal > 0 ? (fakeProfilesCount / scoredTotal) * 100 : 0;
    const postureRaw = Math.round(100 - (avgRiskScore * 0.4 + highRiskPct * 1.2));
    const calculatedPosture = scoredTotal === 0 ? 100 : Math.max(0, Math.min(100, isNaN(postureRaw) ? 100 : postureRaw));
    
    let bannerPostureLabel = "Critical";
    let bannerBorder = "border-[rgba(239,68,68,0.3)]";
    let bannerBg = "bg-[rgba(239,68,68,0.06)]";
    let bannerText = "text-[var(--risk-high)]";
    if (calculatedPosture >= 80) {
        bannerPostureLabel = "Secure";
        bannerBorder = "border-[rgba(16,185,129,0.3)]";
        bannerBg = "bg-[rgba(16,185,129,0.06)]";
        bannerText = "text-[var(--risk-low)]";
    } else if (calculatedPosture >= 60) {
        bannerPostureLabel = "Watch";
        bannerBorder = "border-[rgba(245,158,11,0.3)]";
        bannerBg = "bg-[rgba(245,158,11,0.06)]";
        bannerText = "text-[var(--risk-med)]";
    } else if (calculatedPosture >= 40) {
        bannerPostureLabel = "Elevated";
        bannerBorder = "border-[rgba(249,115,22,0.3)]";
        bannerBg = "bg-[rgba(249,115,22,0.06)]";
        bannerText = "text-[#f97316]";
    }

    // Sparklines from scan_volume
    const scanVolume = useMemo(() => summary?.scan_volume || [], [summary?.scan_volume]);

    const totalSparkline = useMemo(() => {
        if (!Array.isArray(scanVolume) || scanVolume.length === 0) return [];
        return scanVolume.map(item => ({
            value: Number(item.scans ?? item.count ?? 0)
        }));
    }, [scanVolume]);

    // Total Scans delta
    const totalScansDelta = useMemo(() => {
        if (!Array.isArray(scanVolume) || scanVolume.length < 7) {
            return { text: "—", footnote: "last 7d vs prior 7d" };
        }
        const last7Days = scanVolume.slice(-7);
        const prior7Days = scanVolume.length >= 14 ? scanVolume.slice(-14, -7) : [];

        const last7Sum = last7Days.reduce((sum, d) => sum + Number(d.scans ?? d.count ?? 0), 0);
        const prior7Sum = prior7Days.reduce((sum, d) => sum + Number(d.scans ?? d.count ?? 0), 0);

        if (prior7Sum > 0) {
            const diffPct = ((last7Sum - prior7Sum) / prior7Sum) * 100;
            return {
                text: `${diffPct >= 0 ? "+" : ""}${diffPct.toFixed(1)}%`,
                footnote: "vs prior 7d"
            };
        } else if (last7Sum > 0) {
            return { text: "+100%", footnote: "vs prior 7d" };
        }
        return { text: "0.0%", footnote: "vs prior 7d" };
    }, [scanVolume]);

    // Share rates
    const fakeRatePct = scoredTotal > 0 ? (fakeProfilesCount / scoredTotal) * 100 : 0;
    const authRatePct = scoredTotal > 0 ? (authenticProfilesCount / scoredTotal) * 100 : 0;

    const fakeRateText = scoredTotal > 0 ? `${fakeRatePct.toFixed(1)}% fake` : "—";
    const authCardFootnote = `${authRatePct.toFixed(1)}% clean · ${formatNumber(reviewCount)} need review`;

    // Model accuracy & ROC-AUC
    const numericAccuracy = useMemo(() => {
        if (modelMetrics?.test_accuracy != null) return Number(modelMetrics.test_accuracy) * 100;
        if (modelMetrics?.validation_metrics?.f1 != null) return Number(modelMetrics.validation_metrics.f1) * 100;
        return null;
    }, [modelMetrics]);

    const rocAucVal = useMemo(() => {
        if (modelMetrics?.test_roc_auc != null) {
            return `ROC-AUC ${Number(modelMetrics.test_roc_auc).toFixed(3)}`;
        }
        if (modelMetrics?.validation_metrics?.roc_auc != null) {
            return `ROC-AUC ${Number(modelMetrics.validation_metrics.roc_auc).toFixed(3)}`;
        }
        return "—";
    }, [modelMetrics]);

    // ----------------------------------------------------------
    // Scan Activity Chart Filtering with 7D Moving Average
    // ----------------------------------------------------------
    const activityChartData = useMemo(() => {
        if (!Array.isArray(scanVolume) || scanVolume.length === 0) return [];
        let items = scanVolume;
        if (timeRange === "7D") {
            items = scanVolume.slice(-7);
        } else {
            items = scanVolume;
        }

        let runningCumulative = 0;
        const rawPoints = items.map(d => {
            const scans = Number(d.scans ?? d.count ?? 0);
            runningCumulative += scans;
            return {
                rawDate: d.date,
                date: d.date,
                scans,
                cumulative: runningCumulative,
                fake: Number(d.fake ?? 0),
                authentic: Number(d.authentic ?? 0),
            };
        });

        return rawPoints.map((point, idx, arr) => {
            const windowStart = Math.max(0, idx - 6);
            const windowSlice = arr.slice(windowStart, idx + 1);
            const windowSum = windowSlice.reduce((s, p) => s + p.scans, 0);
            const ma7 = windowSum / windowSlice.length;
            return {
                ...point,
                ma7: Math.round(ma7 * 10) / 10
            };
        });
    }, [scanVolume, timeRange]);

    const chartStats = useMemo(() => {
        if (!activityChartData || activityChartData.length === 0) {
            return { peak: 0, peakDate: "—", dailyAvg: "0.0", activeDays: 0, totalDays: 0 };
        }
        let peak = 0;
        let peakDate = "—";
        let sum = 0;
        let active = 0;

        for (const item of activityChartData) {
            const scans = item.scans || 0;
            sum += scans;
            if (scans > 0) active += 1;
            if (scans > peak) {
                peak = scans;
                try {
                    const d = new Date(item.date);
                    peakDate = isNaN(d.getTime()) ? item.date : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
                } catch {
                    peakDate = item.date;
                }
            }
        }
        if (peak === 0 && activityChartData.length > 0) {
            peakDate = "None";
        }

        const dailyAvg = (sum / activityChartData.length).toFixed(1);

        return {
            peak,
            peakDate,
            dailyAvg,
            activeDays: active,
            totalDays: activityChartData.length
        };
    }, [activityChartData]);

    // 30-Day Heat Strip Data
    const heatStripData = useMemo(() => {
        if (!Array.isArray(scanVolume) || scanVolume.length === 0) return [];
        const last30 = scanVolume.slice(-30);
        let maxScans = 0;
        for (const d of last30) {
            const count = Number(d.scans ?? d.count ?? 0);
            if (count > maxScans) maxScans = count;
        }
        return last30.map(d => {
            const scans = Number(d.scans ?? d.count ?? 0);
            const intensity = maxScans > 0 ? Math.round((scans / maxScans) * 100) : 0;
            return {
                date: d.date,
                scans,
                fake: Number(d.fake ?? 0),
                authentic: Number(d.authentic ?? 0),
                intensity
            };
        });
    }, [scanVolume]);

    // ----------------------------------------------------------
    // Risk Distribution Donut Data
    // ----------------------------------------------------------
    const donutData = useMemo(() => {
        const c = analytics?.classification_counts;
        if (!c) return [];
        return [
            { name: "Low Risk", value: c.low || 0, color: "var(--risk-low)", level: "low" },
            { name: "Medium Risk", value: c.medium || 0, color: "var(--risk-med)", level: "medium" },
            { name: "High Risk", value: c.high || 0, color: "var(--risk-high)", level: "high" },
            { name: "Critical Risk", value: c.very_high || 0, color: "var(--risk-vhigh)", level: "very_high" },
            { name: "Insufficient Data", value: c.insufficient_data || 0, color: "var(--text-muted)", level: "insufficient_data" },
        ].filter(d => d.value > 0);
    }, [analytics]);

    // ----------------------------------------------------------
    // Recent Scans Table: Collapse Repeats & Filter Chips
    // ----------------------------------------------------------
    const collapsedScans = useMemo(() => {
        if (!Array.isArray(recentScans) || recentScans.length === 0) return [];
        const map = new Map();
        for (const scan of recentScans) {
            const rawProfile = (scan.profile || scan.username || "unknown").trim();
            const rawPlatform = (scan.platform || "unknown").trim();
            const key = `${rawProfile.toLowerCase()}_${rawPlatform.toLowerCase()}`;
            if (map.has(key)) {
                const existing = map.get(key);
                existing.repeatCount += 1;
            } else {
                map.set(key, {
                    ...scan,
                    repeatCount: 1,
                });
            }
        }
        return Array.from(map.values());
    }, [recentScans]);

    const filteredScans = useMemo(() => {
        return collapsedScans.filter(s => {
            let matchesRisk = true;
            if (filterRisk === "low") matchesRisk = s.risk_level === "low";
            else if (filterRisk === "medium") matchesRisk = s.risk_level === "medium";
            else if (filterRisk === "high") matchesRisk = s.risk_level === "high" || s.risk_level === "very_high";

            const q = scanSearchQuery.toLowerCase().trim();
            const matchesSearch = !q || 
                (s.profile || s.username || "").toLowerCase().includes(q) ||
                (s.platform || "").toLowerCase().includes(q);

            return matchesRisk && matchesSearch;
        });
    }, [collapsedScans, filterRisk, scanSearchQuery]);

    // Watchlist deduplication
    const deduplicatedWatchlist = useMemo(() => {
        const scans = analytics?.top_risky_scans;
        if (!Array.isArray(scans) || scans.length === 0) return [];
        const seen = new Set();
        const result = [];
        for (const scan of scans) {
            const u = (scan.username || "").trim().toLowerCase();
            const p = (scan.platform || "").trim().toLowerCase();
            const key = `${u}::${p}`;
            if (!seen.has(key)) {
                seen.add(key);
                result.push(scan);
            }
        }
        return result.slice(0, 4);
    }, [analytics?.top_risky_scans]);

    const handleRescanProfile = useCallback((identifier) => {
        const cleanHandle = (identifier || "").replace(/^@/, "").trim();
        if (onSearch && cleanHandle) {
            onSearch(cleanHandle);
        } else if (onNavigate) {
            onNavigate("scanner");
        }
    }, [onSearch, onNavigate]);

    // Dynamic AI Security Insights
    const aiInsights = useMemo(() => {
        const insights = [];

        // 1. Threat Prevalence
        if (scoredTotal > 0) {
            const rate = fakeRatePct;
            if (rate >= 25) {
                insights.push({
                    id: "rate-elevated",
                    tone: "fake",
                    icon: AlertTriangle,
                    title: "Elevated threat prevalence",
                    description: `${rate.toFixed(1)}% of audited profiles show synthetic bot patterns over the last ${rangeLabel}. Stricter verification advised.`,
                    bg: "var(--kpi-fake-bg)",
                    border: "var(--kpi-fake-icon)"
                });
            } else if (rate >= 10) {
                insights.push({
                    id: "rate-moderate",
                    tone: "warn",
                    icon: AlertTriangle,
                    title: "Moderate threat prevalence",
                    description: `${rate.toFixed(1)}% fake detection rate observed over the last ${rangeLabel}. Baseline risk level maintained.`,
                    bg: "var(--sys-status-bg)",
                    border: "var(--risk-med)"
                });
            } else {
                insights.push({
                    id: "rate-healthy",
                    tone: "auth",
                    icon: ShieldCheck,
                    title: "Low threat exposure",
                    description: `Only ${rate.toFixed(1)}% of inspected profiles flagged as high risk over the last ${rangeLabel}. Account authenticity remains solid.`,
                    bg: "var(--kpi-auth-bg)",
                    border: "var(--kpi-auth-icon)"
                });
            }
        }

        // 2. Primary risk vector
        const comp = analytics?.average_risk_components;
        if (comp && (comp.ml_risk > 0 || comp.nlp_risk > 0 || comp.rule_risk > 0)) {
            const highestSignal = Object.entries(comp).sort((a, b) => b[1] - a[1])[0];
            if (highestSignal) {
                const [sigKey, sigVal] = highestSignal;
                let sigTitle = "Primary Vector: Behavioral ML";
                let sigDesc = `Behavioral & interaction anomalies are the strongest detection vector across your scans (${sigVal.toFixed(1)}/100 avg).`;
                if (sigKey === "nlp_risk") {
                    sigTitle = "Primary Vector: Lexical & Bio";
                    sigDesc = `Bio spam markers, phishing keywords, and suspicious grammar represent your highest threat signals (${sigVal.toFixed(1)}/100 avg).`;
                } else if (sigKey === "rule_risk") {
                    sigTitle = "Primary Vector: Heuristic Metadata";
                    sigDesc = `Account age, follower/following ratios, and missing avatars account for the dominant flags (${sigVal.toFixed(1)}/100 avg).`;
                }
                insights.push({
                    id: "signal-dominant",
                    tone: "model",
                    icon: Brain,
                    title: sigTitle,
                    description: sigDesc,
                    bg: "var(--kpi-model-bg)",
                    border: "var(--kpi-model-icon)"
                });
            }
        }

        // 3. Platform concentration
        const platCounts = analytics?.platform_counts;
        if (platCounts && Object.keys(platCounts).length > 0) {
            const topPlat = Object.entries(platCounts)[0];
            if (topPlat) {
                const [platName, pCount] = topPlat;
                const platShare = totalScans > 0 ? ((pCount / totalScans) * 100).toFixed(0) : 100;
                insights.push({
                    id: "platform-concentration",
                    tone: "total",
                    icon: Layers,
                    title: `Platform concentration: ${platName.charAt(0).toUpperCase() + platName.slice(1)}`,
                    description: `${platName.charAt(0).toUpperCase() + platName.slice(1)} accounts for ${platShare}% of all analyzed profiles (${formatNumber(pCount)} profile${pCount === 1 ? "" : "s"}).`,
                    bg: "var(--kpi-total-bg)",
                    border: "var(--kpi-total-icon)"
                });
            }
        }

        // 4. Review backlog if review >= 10
        if (reviewCount >= 10) {
            insights.push({
                id: "review-backlog",
                tone: "warn",
                icon: Clock,
                title: "Manual review backlog",
                description: `${formatNumber(reviewCount)} suspicious accounts are flagged in medium-risk triage awaiting manual review decisions.`,
                bg: "var(--sys-status-bg)",
                border: "var(--risk-med)"
            });
        }

        // 5. Data coverage gap if insufficient >= 5% of total
        if (insights.length < 4 && insufficientCount > 0 && totalScans > 0 && (insufficientCount / totalScans >= 0.05 || insufficientCount >= 2)) {
            const gapPct = ((insufficientCount / totalScans) * 100).toFixed(1);
            insights.push({
                id: "data-coverage-gap",
                tone: "warn",
                icon: ShieldAlert,
                title: "Data coverage gap",
                description: `${formatNumber(insufficientCount)} profile${insufficientCount === 1 ? "" : "s"} (${gapPct}%) lacked public metadata over the last ${rangeLabel}. Manual fallback recommended.`,
                bg: "var(--bg-surface-secondary)",
                border: "var(--border-hover)"
            });
        }

        // 6. Fallback model calibration
        if (insights.length < 4 && modelMetrics?.validation_metrics?.roc_auc) {
            insights.push({
                id: "model-calibration",
                tone: "model",
                icon: Activity,
                title: "Model Calibration Online",
                description: `Calibrated v4 ensemble operational with ROC-AUC ${Number(modelMetrics.validation_metrics.roc_auc).toFixed(3)}. Truthful confidence scores enabled.`,
                bg: "var(--kpi-model-bg)",
                border: "var(--kpi-model-icon)"
            });
        }

        return insights.slice(0, 4);
    }, [scoredTotal, fakeRatePct, rangeLabel, analytics, reviewCount, insufficientCount, totalScans, modelMetrics]);

    const isCompact = prefs.density === "compact";
    const animationsEnabled = prefs.animations !== false;
    const isCustomized = prefs.hidden.length > 0 || detectActivePreset(prefs) !== "default";

    // ----------------------------------------------------------
    // Render Widget by ID (Config-Driven 12-Column Engine)
    // ----------------------------------------------------------
    const renderWidget = (id) => {
        if (prefs.hidden.includes(id)) return null;
        const config = DEFAULT_WIDGETS.find(w => w.id === id);
        if (!config) return null;

        // Dynamic span classes based on 12-col grid
        const spanClass = config.span === 8 ? "col-span-12 lg:col-span-8" : "col-span-12 lg:col-span-4";

        switch (id) {
            case "posture":
                return (
                    <div key={id} className={spanClass}>
                        {loading ? (
                            <div className="skeleton h-[330px] rounded-2xl" />
                        ) : (
                            <ThreatPostureGauge 
                                avgRiskScore={avgRiskScore}
                                fakeCount={fakeProfilesCount}
                                scoredTotal={scoredTotal}
                                reviewCount={reviewCount}
                                authCount={authenticProfilesCount}
                                isCompact={isCompact}
                                animationsEnabled={animationsEnabled}
                            />
                        )}
                    </div>
                );

            case "kpis":
                return (
                    <div key={id} className={spanClass}>
                        {loading ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                {Array(4).fill(0).map((_, i) => (
                                    <div key={i} className={`skeleton h-[155px] rounded-2xl stagger-${i+1}`} />
                                ))}
                            </div>
                        ) : (
                            <div className={`grid grid-cols-1 sm:grid-cols-2 ${isCompact ? "gap-3" : "gap-4"}`}>
                                <KpiCard 
                                    label="Total Scans"
                                    numericValue={totalScans}
                                    deltaText={totalScansDelta.text}
                                    deltaFootnote={totalScansDelta.footnote}
                                    icon={Activity}
                                    type="total"
                                    sparklineData={totalSparkline}
                                    isTotalCard={true}
                                    isCompact={isCompact}
                                    animationsEnabled={animationsEnabled}
                                />
                                <KpiCard 
                                    label="High-Risk Profiles"
                                    numericValue={fakeProfilesCount}
                                    footnote={fakeRateText}
                                    progressVal={fakeRatePct}
                                    progressColor="var(--risk-high)"
                                    icon={AlertTriangle}
                                    type="fake"
                                    isCompact={isCompact}
                                    animationsEnabled={animationsEnabled}
                                />
                                <KpiCard 
                                    label="Authentic Profiles"
                                    numericValue={authenticProfilesCount}
                                    footnote={authCardFootnote}
                                    progressVal={authRatePct}
                                    progressColor="var(--risk-low)"
                                    icon={ShieldCheck}
                                    type="auth"
                                    isCompact={isCompact}
                                    animationsEnabled={animationsEnabled}
                                />
                                <KpiCard 
                                    label="Model Accuracy"
                                    numericValue={numericAccuracy}
                                    displaySuffix="%"
                                    footnote={rocAucVal}
                                    progressVal={numericAccuracy || 0}
                                    progressColor="var(--kpi-model-icon)"
                                    icon={Brain}
                                    type="model"
                                    isCompact={isCompact}
                                    animationsEnabled={animationsEnabled}
                                />
                            </div>
                        )}
                    </div>
                );

            case "activity":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact}>
                            <CardHeader 
                                title="Scan Activity" 
                                icon={Activity} 
                                subtitle={timeRange === "90D" || timeRange === "1Y" 
                                    ? "*30-day retention active; displaying latest 30 days." 
                                    : (activityChartMode === "cumulative" ? "Cumulative profile throughput" : "Daily profile verification throughput")
                                }
                                action={
                                    <div className="flex items-center gap-1.5">
                                        {/* Daily / Cumulative Toggle */}
                                        <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                            <button
                                                onClick={() => setActivityChartMode("daily")}
                                                className={`px-2.5 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                                    activityChartMode === "daily"
                                                        ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs"
                                                        : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                                }`}
                                            >
                                                Daily
                                            </button>
                                            <button
                                                onClick={() => setActivityChartMode("cumulative")}
                                                className={`px-2.5 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                                    activityChartMode === "cumulative"
                                                        ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs"
                                                        : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                                }`}
                                            >
                                                Total
                                            </button>
                                        </div>
                                    </div>
                                }
                            />

                            {loading ? (
                                <div className="skeleton h-[280px] rounded-xl w-full" />
                            ) : activityChartData.length > 0 ? (
                                <div className="space-y-3">
                                    {/* Stat Strip */}
                                    <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-1.5 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] text-xs">
                                        <div className="flex items-center gap-3 md:gap-4 flex-wrap">
                                            <div>
                                                <span className="text-[var(--text-muted)] font-normal">Peak: </span>
                                                <span className="font-bold text-[var(--text-primary)] font-mono">{formatNumber(chartStats.peak)}</span>
                                                {chartStats.peakDate && <span className="text-[var(--text-muted)] ml-1 font-normal">({chartStats.peakDate})</span>}
                                            </div>
                                            <div className="w-[1px] h-3 bg-[var(--border-inner)] hidden sm:block" />
                                            <div>
                                                <span className="text-[var(--text-muted)] font-normal">Daily avg: </span>
                                                <span className="font-bold text-[var(--text-primary)] font-mono">{chartStats.dailyAvg}</span>
                                            </div>
                                            <div className="w-[1px] h-3 bg-[var(--border-inner)] hidden sm:block" />
                                            <div>
                                                <span className="text-[var(--text-muted)] font-normal">Active days: </span>
                                                <span className="font-bold text-[var(--text-primary)] font-mono">{chartStats.activeDays}/{chartStats.totalDays}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-3 text-[11px] font-medium text-[var(--text-secondary)]">
                                            <div className="flex items-center gap-1.5">
                                                <span className="w-3 h-0.5 bg-[var(--accent)] rounded-full" />
                                                <span>{activityChartMode === "cumulative" ? "Cumulative" : "Daily Scans"}</span>
                                            </div>
                                            {activityChartMode === "daily" && (
                                                <div className="flex items-center gap-1.5">
                                                    <span className="w-3 h-0.5 border-t-2 border-dashed border-[var(--risk-med)]" />
                                                    <span>7D Avg</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Area Chart */}
                                    <div style={{ height: isCompact ? 210 : 255 }} className="w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <AreaChart data={activityChartData} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                                                <defs>
                                                    <linearGradient id="colorScans" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                                                        <stop offset="95%" stopColor="var(--accent)" stopOpacity={0.0}/>
                                                    </linearGradient>
                                                </defs>
                                                <XAxis 
                                                    dataKey="date" 
                                                    stroke="var(--border-inner)" 
                                                    tick={{ fill: "var(--text-muted)", fontSize: 11, fontWeight: 500 }} 
                                                    tickLine={false} 
                                                    axisLine={false}
                                                    tickFormatter={(val) => {
                                                        try {
                                                            const d = new Date(val);
                                                            return isNaN(d.getTime()) ? val : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
                                                        } catch {
                                                            return val;
                                                        }
                                                    }}
                                                />
                                                <YAxis 
                                                    stroke="var(--border-inner)" 
                                                    tick={{ fill: "var(--text-muted)", fontSize: 11, fontWeight: 500 }} 
                                                    tickLine={false} 
                                                    axisLine={false}
                                                    allowDecimals={false}
                                                    width={32}
                                                />
                                                <Tooltip 
                                                    contentStyle={{ 
                                                        background: "var(--bg-card)", 
                                                        backdropFilter: "blur(12px)", 
                                                        WebkitBackdropFilter: "blur(12px)",
                                                        border: "1px solid var(--border-hover)", 
                                                        borderRadius: "12px", 
                                                        color: "var(--text-primary)", 
                                                        boxShadow: "var(--shadow-md)",
                                                        padding: "8px 12px"
                                                    }}
                                                    itemStyle={{ color: "var(--text-primary)", fontWeight: 700 }}
                                                    labelStyle={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 4 }}
                                                />
                                                <Area 
                                                    type="monotone" 
                                                    dataKey={activityChartMode === "cumulative" ? "cumulative" : "scans"} 
                                                    name={activityChartMode === "cumulative" ? "Cumulative Scans" : "Daily Scans"} 
                                                    stroke="var(--accent)" 
                                                    strokeWidth={2} 
                                                    fillOpacity={1} 
                                                    fill="url(#colorScans)" 
                                                />
                                                {activityChartMode === "daily" && (
                                                    <Line 
                                                        type="monotone" 
                                                        dataKey="ma7" 
                                                        name="7D Moving Avg" 
                                                        stroke="var(--risk-med)" 
                                                        strokeWidth={2} 
                                                        strokeDasharray="4 4" 
                                                        dot={false} 
                                                        isAnimationActive={false} 
                                                    />
                                                )}
                                            </AreaChart>
                                        </ResponsiveContainer>
                                    </div>

                                    {/* 30-Day Heat Strip */}
                                    {heatStripData.length > 0 && (
                                        <div className="pt-2.5 border-t border-[var(--border-inner)]">
                                            <div className="flex items-center justify-between text-[11px] font-semibold text-[var(--text-muted)] mb-1.5">
                                                <span>30-Day Activity Heatmap</span>
                                                <span className="font-mono text-[10px]">Peak: {formatNumber(chartStats.peak)} / day</span>
                                            </div>
                                            <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                                                {heatStripData.map((d, i) => (
                                                    <div 
                                                        key={i}
                                                        className="w-4 h-4 sm:w-5 sm:h-5 rounded-[4px] border border-[var(--border-inner)] shrink-0 transition-transform hover:scale-125 cursor-pointer shadow-xs"
                                                        style={{ 
                                                            backgroundColor: d.scans > 0 
                                                                ? `color-mix(in srgb, var(--accent) ${Math.max(20, d.intensity)}%, var(--bg-surface-secondary))` 
                                                                : "var(--bg-surface-secondary)" 
                                                        }}
                                                        title={`${d.date}: ${formatNumber(d.scans)} scan${d.scans === 1 ? "" : "s"} (${formatNumber(d.fake)} high-risk, ${formatNumber(d.authentic)} clear)`}
                                                    />
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="h-[240px] flex flex-col items-center justify-center text-[var(--text-muted)] text-sm">
                                    <Activity size={28} className="mb-2 opacity-40" />
                                    <span>No scan activity recorded for this period</span>
                                </div>
                            )}
                        </BaseCard>
                    </div>
                );

            case "distribution":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact} className="h-full flex flex-col justify-between">
                            <CardHeader 
                                title="Risk Distribution" 
                                icon={ShieldAlert} 
                                subtitle="Classification breakdown"
                            />

                            {loading ? (
                                <div className="skeleton h-[240px] rounded-xl w-full" />
                            ) : donutData.length > 0 ? (
                                <div className="flex flex-col h-full justify-between">
                                    <div className="relative flex items-center justify-center h-[180px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie 
                                                    data={donutData} 
                                                    innerRadius="68%" 
                                                    outerRadius="88%" 
                                                    paddingAngle={4} 
                                                    cornerRadius={4}
                                                    dataKey="value" 
                                                    stroke="none"
                                                >
                                                    {donutData.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                                    ))}
                                                </Pie>
                                                <Tooltip 
                                                    contentStyle={{ 
                                                        background: "var(--bg-card)", 
                                                        border: "1px solid var(--border-inner)", 
                                                        borderRadius: "10px",
                                                        color: "var(--text-primary)"
                                                    }}
                                                    itemStyle={{ color: "var(--text-primary)", fontWeight: "bold", fontSize: 13 }}
                                                />
                                            </PieChart>
                                        </ResponsiveContainer>
                                        
                                        {/* Center Count */}
                                        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                            <span className="text-2xl font-bold text-[var(--text-primary)] font-mono tabular-nums leading-none">
                                                {formatNumber(fakeProfilesCount)}
                                            </span>
                                            <span className="text-[10px] uppercase tracking-wider text-[var(--risk-high)] font-extrabold mt-1">
                                                Threats Flagged
                                            </span>
                                        </div>
                                    </div>

                                    {/* Donut Legend */}
                                    <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-[var(--border-inner)]">
                                        {donutData.map((d, i) => (
                                            <div key={i} className="flex items-center justify-between p-1.5 rounded-lg bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                                                <div className="flex items-center gap-1.5 overflow-hidden">
                                                    <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                                                    <span className="text-xs font-medium text-[var(--text-secondary)] truncate">{d.name}</span>
                                                </div>
                                                <span className="text-xs font-bold text-[var(--text-primary)] font-mono tabular-nums ml-1">
                                                    {formatNumber(d.value)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="h-[220px] flex flex-col items-center justify-center text-[var(--text-muted)] text-sm">
                                    <ShieldAlert size={28} className="mb-2 opacity-40" />
                                    <span>No classification records available</span>
                                </div>
                            )}
                        </BaseCard>
                    </div>
                );

            case "signals":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact} className="h-full">
                            <CardHeader 
                                title="Risk Signals" 
                                icon={Activity} 
                                subtitle="Multi-modal engine component averages"
                            />

                            {loading ? (
                                <div className="skeleton h-[180px] rounded-xl" />
                            ) : (
                                <div className="space-y-3">
                                    {[
                                        { key: "ml_risk", label: "Behavioral ML Ensemble", desc: "Account age, ratio & engagement metrics" },
                                        { key: "nlp_risk", label: "Semantic Bio & NLP", desc: "Lexical patterns, spam keywords & links" },
                                        { key: "rule_risk", label: "Heuristic Metadata", desc: "Default avatars, missing info & flags" }
                                    ].map(({ key, label, desc }) => {
                                        const score = analytics?.average_risk_components?.[key];
                                        const hasScore = score != null && !isNaN(score);
                                        const num = hasScore ? score : 0;
                                        const color = num >= 60 ? "var(--risk-high)" : num >= 35 ? "var(--risk-med)" : "var(--risk-low)";
                                        
                                        return (
                                            <div key={key} className="p-2.5 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                                                <div className="flex justify-between items-center mb-0.5">
                                                    <span className="text-xs font-semibold text-[var(--text-primary)]">{label}</span>
                                                    <span className="text-xs font-bold font-mono tabular-nums" style={{ color: hasScore ? color : "var(--text-muted)" }}>
                                                        {hasScore ? `${num.toFixed(1)} / 100` : "— / 100"}
                                                    </span>
                                                </div>
                                                <div className="text-[10px] text-[var(--text-muted)] mb-1.5">{desc}</div>
                                                <div className="w-full bg-[var(--border-inner)] h-1.5 rounded-full overflow-hidden">
                                                    <div 
                                                        className="h-full rounded-full transition-all duration-500" 
                                                        style={{ width: `${Math.min(100, Math.max(0, num))}%`, backgroundColor: color }} 
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </BaseCard>
                    </div>
                );

            case "platform":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact} className="h-full">
                            <CardHeader 
                                title="Platform Mix" 
                                icon={Layers} 
                                subtitle="Distribution across audited networks"
                            />

                            {loading ? (
                                <div className="skeleton h-[180px] rounded-xl" />
                            ) : analytics?.platform_counts && Object.keys(analytics.platform_counts).length > 0 ? (
                                <div className="space-y-2.5">
                                    {Object.entries(analytics.platform_counts).slice(0, 4).map(([plat, count]) => {
                                        const pct = totalScans > 0 ? ((count / totalScans) * 100).toFixed(1) : "0.0";
                                        return (
                                            <div key={plat} className="p-2.5 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                                                <div className="flex justify-between items-center text-xs font-semibold mb-1">
                                                    <span className="capitalize text-[var(--text-primary)] flex items-center gap-1.5">
                                                        <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                                                        {plat}
                                                    </span>
                                                    <span className="text-[var(--text-secondary)] font-mono tabular-nums">
                                                        {formatNumber(count)} ({pct}%)
                                                    </span>
                                                </div>
                                                <div className="w-full bg-[var(--border-inner)] h-1.5 rounded-full overflow-hidden">
                                                    <div 
                                                        className="h-full rounded-full bg-[var(--accent)] transition-all duration-500" 
                                                        style={{ width: `${Math.min(100, parseFloat(pct))}%` }} 
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="h-[180px] flex flex-col items-center justify-center text-[var(--text-muted)] text-sm">
                                    <Radio size={24} className="mb-2 opacity-40" />
                                    <span>No platform records found</span>
                                </div>
                            )}
                        </BaseCard>
                    </div>
                );

            case "watchlist":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact} className="h-full">
                            <CardHeader 
                                title="High-Risk Watchlist" 
                                icon={ShieldAlert} 
                                subtitle="Highest scored profiles under surveillance"
                                action={
                                    <button 
                                        onClick={() => onNavigate && onNavigate("history")} 
                                        className="text-xs font-semibold text-[var(--accent-light)] hover:underline cursor-pointer"
                                    >
                                        View All →
                                    </button>
                                }
                            />

                            {loading ? (
                                <div className="skeleton h-[180px] rounded-xl" />
                            ) : deduplicatedWatchlist.length > 0 ? (
                                <div className="space-y-2">
                                    {deduplicatedWatchlist.map((scan, i) => (
                                        <div 
                                            key={scan.scan_id || `${scan.username}_${i}`}
                                            onClick={() => handleRescanProfile(scan.username)}
                                            className="p-2 rounded-xl bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] hover:border-[var(--accent)] flex items-center justify-between transition-all cursor-pointer group hover:bg-[var(--bg-card)] focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                                            title={`Click to re-scan @${scan.username}`}
                                            tabIndex={0}
                                        >
                                            <div className="flex items-center gap-2.5 min-w-0">
                                                <div className="w-6 h-6 rounded-full bg-[rgba(239,68,68,0.1)] text-[var(--risk-high)] border border-[rgba(239,68,68,0.2)] flex items-center justify-center text-[10px] font-bold shrink-0">
                                                    {scan.platform?.charAt(0)?.toUpperCase() || "@"}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className="text-xs font-semibold text-[var(--text-primary)] truncate group-hover:text-[var(--accent-light)] transition-colors">
                                                        @{scan.username || "unknown"}
                                                    </div>
                                                    <div className="text-[10px] text-[var(--text-muted)] truncate">
                                                        {scan.platform || "Instagram"} • {formatRelativeTime(scan.timestamp)}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1.5 shrink-0 ml-2">
                                                <span className="badge badge-fake text-[10px]">
                                                    {scan.final_score != null ? `${Math.round(scan.final_score)}%` : "High"}
                                                </span>
                                                <ChevronRight size={13} className="text-[var(--text-muted)] group-hover:translate-x-0.5 transition-transform" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="h-[180px] flex flex-col items-center justify-center text-[var(--text-muted)] text-sm text-center">
                                    <ShieldCheck size={24} className="mb-1 text-[var(--risk-low)] opacity-70" />
                                    <span className="text-xs">No high-risk accounts detected.</span>
                                </div>
                            )}
                        </BaseCard>
                    </div>
                );

            case "recent":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact}>
                            <CardHeader 
                                title="Recent Scans" 
                                icon={Clock} 
                                subtitle="Latest profile inspections with repeat deduplication"
                                action={
                                    <div className="flex flex-wrap items-center gap-2.5">
                                        <div className="relative">
                                            <Search size={12} className="absolute left-2.5 top-2.5 text-[var(--text-muted)]" />
                                            <input
                                                type="text"
                                                value={scanSearchQuery}
                                                onChange={(e) => setScanSearchQuery(e.target.value)}
                                                placeholder="Filter handle or platform..."
                                                className="pl-7 pr-2 py-1 text-xs rounded-lg border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[var(--accent)] w-36 sm:w-44 transition-all"
                                            />
                                        </div>

                                        <div className="hidden sm:flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                                            {[
                                                { id: "all", label: "All" },
                                                { id: "low", label: "Low" },
                                                { id: "medium", label: "Med" },
                                                { id: "high", label: "High+" },
                                            ].map(f => (
                                                <button
                                                    key={f.id}
                                                    onClick={() => setFilterRisk(f.id)}
                                                    className={`px-2 py-0.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                                                        filterRisk === f.id
                                                            ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs"
                                                            : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                                                    }`}
                                                >
                                                    {f.label}
                                                </button>
                                            ))}
                                        </div>

                                        <button 
                                            id="btn-view-all-history"
                                            className="text-xs font-semibold text-[var(--accent-light)] hover:underline cursor-pointer" 
                                            onClick={() => onNavigate && onNavigate("history")}
                                        >
                                            View All →
                                        </button>
                                    </div>
                                }
                            />

                            <div className="overflow-x-auto -mx-4 sm:-mx-6 px-4 sm:px-6">
                                <table className="w-full text-left border-collapse min-w-[580px]">
                                    <thead className="sticky top-0 bg-[var(--bg-card)] z-10">
                                        <tr>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)]">Profile</th>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)]">Platform</th>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)]">Risk Meter</th>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)]">Status</th>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)]">Time</th>
                                            <th className="pb-2.5 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-bold border-b border-[var(--border-inner)] text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {loading ? (
                                            Array(4).fill(0).map((_, i) => (
                                                <tr key={i}>
                                                    <td className="py-3 border-b border-[var(--border-inner)]"><div className="skeleton h-4 w-28 rounded-lg" /></td>
                                                    <td className="py-3 border-b border-[var(--border-inner)]"><div className="skeleton h-4 w-16 rounded-lg" /></td>
                                                    <td className="py-3 border-b border-[var(--border-inner)]"><div className="skeleton h-4 w-20 rounded-lg" /></td>
                                                    <td className="py-3 border-b border-[var(--border-inner)]"><div className="skeleton h-5 w-16 rounded-full" /></td>
                                                    <td className="py-3 border-b border-[var(--border-inner)]"><div className="skeleton h-4 w-14 rounded-lg" /></td>
                                                    <td className="py-3 border-b border-[var(--border-inner)] text-right"><div className="skeleton h-6 w-6 rounded ml-auto" /></td>
                                                </tr>
                                            ))
                                        ) : filteredScans.length > 0 ? (
                                            filteredScans.map((scan, i) => {
                                                const numericScore = parseRiskScore(scan.score);
                                                const barColor = getRiskColor(scan.risk_level);
                                                const badgeClass = getRiskBadgeClass(scan.risk_level);
                                                const handleText = scan.profile || `@${scan.username || "unknown"}`;

                                                return (
                                                    <tr 
                                                        key={scan.scan_id || i} 
                                                        className={`group hover:bg-[var(--bg-surface-secondary)] transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-[var(--accent)] outline-none ${
                                                            isCompact ? "h-9" : "h-11"
                                                        }`}
                                                        onClick={() => onNavigate && onNavigate("history")}
                                                        tabIndex={0}
                                                    >
                                                        {/* Profile with ×N repeat badge */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 py-2">
                                                            <div className="flex items-center gap-2.5">
                                                                <div className="w-7 h-7 rounded-full bg-[var(--bg-surface-secondary)] flex items-center justify-center border border-[var(--border-inner)] text-[10px] font-bold text-[var(--text-primary)] shrink-0">
                                                                    {scan.platform?.charAt(0) || "@"}
                                                                </div>
                                                                <div className="flex items-center gap-1.5 min-w-0">
                                                                    <span 
                                                                        className="font-medium text-[13px] group-hover:text-[var(--accent-light)] transition-colors text-[var(--text-primary)] truncate max-w-[140px] sm:max-w-[200px]"
                                                                        title={handleText}
                                                                    >
                                                                        {handleText}
                                                                    </span>
                                                                    {scan.repeatCount > 1 && (
                                                                        <span 
                                                                            className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-[var(--accent)] text-white shadow-xs" 
                                                                            title={`Profile audited ${scan.repeatCount} times`}
                                                                        >
                                                                            ×{scan.repeatCount}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </td>

                                                        {/* Platform */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 text-[13px] text-[var(--text-secondary)] font-medium py-2">
                                                            {scan.platform || "Unknown"}
                                                        </td>

                                                        {/* Risk Meter */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 py-2">
                                                            <div className="flex items-center gap-2">
                                                                <div className="w-14 h-1.5 rounded-full bg-[var(--border-hover)] overflow-hidden">
                                                                    <div 
                                                                        className="h-full rounded-full transition-all duration-300" 
                                                                        style={{ 
                                                                            width: numericScore != null ? `${numericScore}%` : "0%", 
                                                                            backgroundColor: barColor 
                                                                        }} 
                                                                    />
                                                                </div>
                                                                <span className="text-xs font-semibold font-mono text-[var(--text-primary)] tabular-nums">
                                                                    {numericScore != null ? `${numericScore}%` : "—"}
                                                                </span>
                                                            </div>
                                                        </td>

                                                        {/* Status Badge */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 py-2">
                                                            <span className={`badge ${badgeClass} text-[10px]`}>
                                                                {scan.status || "Evaluated"}
                                                            </span>
                                                        </td>

                                                        {/* Time */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 text-xs text-[var(--text-muted)] font-normal whitespace-nowrap py-2">
                                                            {formatRelativeTime(scan.date || scan.timestamp)}
                                                        </td>

                                                        {/* Actions */}
                                                        <td className="border-b border-[var(--border-inner)] group-last:border-0 text-right py-2">
                                                            <div className="flex items-center justify-end gap-1">
                                                                <button 
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleRescanProfile(scan.profile || scan.username);
                                                                    }}
                                                                    className="p-1 rounded-lg hover:bg-[var(--border-inner)] text-[var(--text-muted)] hover:text-[var(--accent-light)] transition-colors cursor-pointer"
                                                                    title="Rescan profile"
                                                                    aria-label="Rescan"
                                                                >
                                                                    <RotateCw size={13} className="hover:rotate-180 transition-transform duration-300" />
                                                                </button>
                                                                <ChevronRight size={14} className="text-[var(--text-muted)] group-hover:translate-x-0.5 transition-transform" />
                                                            </div>
                                                        </td>
                                                    </tr>
                                                );
                                            })
                                        ) : (
                                            <tr>
                                                <td colSpan="6" className="py-8 text-center text-xs text-[var(--text-muted)]">
                                                    No scans matching current filter.
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </BaseCard>
                    </div>
                );

            case "insights":
                return (
                    <div key={id} className={spanClass}>
                        <BaseCard isCompact={isCompact} className="h-full">
                            <CardHeader 
                                title="AI Security Insights" 
                                icon={Brain} 
                                subtitle="Telemetry-generated synthesis"
                            />

                            <div className="space-y-2.5">
                                {loading ? (
                                    Array(3).fill(0).map((_, i) => (
                                        <div key={i} className="skeleton h-[68px] rounded-xl" />
                                    ))
                                ) : aiInsights.length > 0 ? (
                                    aiInsights.map((insight) => {
                                        const Icon = insight.icon;
                                        return (
                                            <div 
                                                key={insight.id} 
                                                className="p-3 rounded-xl border relative overflow-hidden transition-all duration-200" 
                                                style={{ backgroundColor: insight.bg, borderColor: `${insight.border}35` }}
                                            >
                                                <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: insight.border }} />
                                                <div className="flex items-start gap-2.5">
                                                    <Icon size={15} className="mt-0.5 shrink-0" style={{ color: insight.border }} />
                                                    <div>
                                                        <p className="text-xs font-bold text-[var(--text-primary)] mb-0.5 leading-snug">
                                                            {insight.title}
                                                        </p>
                                                        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                                                            {insight.description}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })
                                ) : (
                                    <div className="h-[180px] flex flex-col items-center justify-center text-[var(--text-muted)] text-xs text-center">
                                        <Brain size={24} className="mb-1 opacity-40" />
                                        <span>Complete initial scans to generate heuristic insights.</span>
                                    </div>
                                )}
                            </div>
                        </BaseCard>
                    </div>
                );

            default:
                return null;
        }
    };

    // Filter order to visible items
    const visibleWidgets = prefs.order.filter(id => !prefs.hidden.includes(id));

    // ==========================================================
    // Render Layout
    // ==========================================================

    return (
        <div className="animate-fade-in p-5 md:p-8 text-[var(--text-primary)] max-w-[1600px] mx-auto w-full box-border relative">
            
            {/* Ambient Background Radial Glow (Reduced opacity to 0.04-0.06 for professional finish) */}
            <div className="absolute top-[-80px] left-[-40px] w-[450px] h-[450px] bg-[var(--accent)] opacity-[0.05] blur-[120px] pointer-events-none rounded-full" />
            <div className="absolute top-[20%] right-[-60px] w-[350px] h-[350px] bg-[#d946ef] opacity-[0.03] blur-[130px] pointer-events-none rounded-full" />

            {/* ===================================================
                1. Compressed Hero (approx 120px height)
            =================================================== */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5 relative z-10">
                {/* Left: Status chip, 28px greeting, one summary sentence */}
                <div className="max-w-2xl">
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold mb-2 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)] text-[var(--accent-light)]">
                        <span className={`w-1.5 h-1.5 rounded-full bg-[var(--risk-low)] ${animationsEnabled ? "animate-pulse" : ""}`} />
                        AI Profile Intelligence Command Center
                    </div>
                    <h1 className="text-2xl md:text-[28px] font-bold tracking-tight text-[var(--text-primary)] mb-1">
                        {greeting}, <span className="gradient-text">{userName}</span>
                    </h1>
                    <p className="text-[var(--text-secondary)] text-xs md:text-sm leading-relaxed line-clamp-2">
                        {heroSummaryText}
                    </p>
                </div>

                {/* Right: Same row, desktop flex-nowrap action buttons */}
                <div className="flex items-center gap-2.5 shrink-0 flex-wrap sm:flex-nowrap">
                    {/* Customize Button with Tooltip and Badge */}
                    <div className="relative">
                        <button
                            ref={customizeBtnRef}
                            id="btn-customize-dashboard"
                            onClick={() => setShowCustomize(true)}
                            className="relative flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all border text-xs font-semibold cursor-pointer hover:bg-[var(--btn-secondary-hover-bg)]"
                            style={{ 
                                backgroundColor: "var(--btn-secondary-bg)", 
                                color: "var(--btn-secondary-text)", 
                                borderColor: "var(--btn-secondary-border)" 
                            }}
                            title={`Customize dashboard layout [C]${isCustomized ? ` · ${prefs.hidden.length} hidden` : ""}`}
                            aria-label="Customize dashboard"
                        >
                            <SlidersHorizontal size={14} />
                            <span>Customize</span>
                            <kbd className="hidden lg:inline text-[10px] ml-1 opacity-60 font-mono">C</kbd>
                            {isCustomized && (
                                <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[var(--accent)] ring-2 ring-[var(--bg-card)]" />
                            )}
                        </button>
                    </div>

                    {/* Export CSV */}
                    <button
                        id="btn-export-report"
                        onClick={handleExportReport}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all border text-xs font-semibold cursor-pointer hover:bg-[var(--btn-secondary-hover-bg)]"
                        style={{ 
                            backgroundColor: "var(--btn-secondary-bg)", 
                            color: "var(--btn-secondary-text)", 
                            borderColor: "var(--btn-secondary-border)" 
                        }}
                        title="Export recent scans CSV [E]"
                    >
                        <Download size={14} />
                        <span>Export CSV</span>
                        <kbd className="hidden lg:inline text-[10px] ml-1 opacity-60 font-mono">E</kbd>
                    </button>

                    {/* Bulk Upload */}
                    <button
                        id="btn-bulk-upload-nav"
                        onClick={() => onNavigate && onNavigate("bulk")}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl transition-all border text-xs font-semibold cursor-pointer hover:bg-[var(--btn-secondary-hover-bg)]"
                        style={{ 
                            backgroundColor: "var(--btn-secondary-bg)", 
                            color: "var(--btn-secondary-text)", 
                            borderColor: "var(--btn-secondary-border)" 
                        }}
                        title="Batch audit handles via CSV [B]"
                    >
                        <Upload size={14} />
                        <span>Bulk Upload</span>
                        <kbd className="hidden lg:inline text-[10px] ml-1 opacity-60 font-mono">B</kbd>
                    </button>

                    {/* Primary New Scan */}
                    <button
                        id="btn-new-scan-nav"
                        onClick={() => onNavigate && onNavigate("scanner")}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer hover:opacity-95 shadow-sm"
                        style={{ 
                            background: "var(--btn-primary-bg)", 
                            color: "var(--text-primary)" 
                        }}
                        title="Start single account inspection [N]"
                    >
                        <Search size={14} color="var(--text-primary)" />
                        <span>New Scan</span>
                        <kbd className="hidden lg:inline text-[10px] ml-1 opacity-80 font-mono">N</kbd>
                    </button>

                    {/* Keyboard Shortcuts Help Button */}
                    <button
                        onClick={() => setShowShortcuts(true)}
                        className="p-2 rounded-xl border border-[var(--btn-secondary-border)] bg-[var(--btn-secondary-bg)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--btn-secondary-hover-bg)] transition-colors cursor-pointer"
                        title="Keyboard shortcuts [?]"
                        aria-label="View keyboard shortcuts"
                    >
                        <HelpCircle size={15} />
                    </button>
                </div>
            </div>

            {/* ===================================================
                2. Slim Sticky Toolbar (Updated time, Live, Global Range)
            =================================================== */}
            <div className="sticky top-0 z-30 bg-[var(--bg-card)]/90 backdrop-blur-md border border-[var(--border-inner)] py-2 px-3.5 rounded-xl mb-5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
                {/* Left: Elapsed time + Refresh button + Live toggle */}
                <div className="flex items-center gap-3 text-xs font-medium text-[var(--text-muted)]">
                    <div className="flex items-center gap-1.5">
                        <Clock size={13} className="text-[var(--text-muted)]" />
                        <span>Updated {timeAgoText}</span>
                    </div>

                    <button 
                        id="btn-dashboard-refresh"
                        onClick={() => loadDashboardData()}
                        disabled={loading}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg border border-[var(--border-inner)] hover:border-[var(--accent)] hover:text-[var(--text-primary)] transition-all bg-[var(--bg-surface-secondary)] cursor-pointer"
                        title="Refresh data [R]"
                    >
                        <RefreshCw size={11} className={loading && animationsEnabled ? "animate-spin text-[var(--accent)]" : ""} />
                        <span>Refresh</span>
                    </button>

                    <button
                        id="btn-dashboard-live"
                        onClick={() => setIsLive(!isLive)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold transition-all border cursor-pointer ${
                            isLive 
                                ? "bg-[rgba(16,185,129,0.12)] border-[var(--risk-low)] text-[var(--risk-low)]" 
                                : "bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
                        }`}
                        title={isLive ? `Live updates active (${prefs.refreshSec || 60}s interval) [L]` : "Click to enable auto-refresh [L]"}
                    >
                        <span className={`w-1.5 h-1.5 rounded-full ${isLive ? "bg-[var(--risk-low)]" : "bg-[var(--text-muted)]"}`} />
                        <span>Live {isLive ? "ON" : "OFF"}</span>
                    </button>
                </div>

                {/* Right: GLOBAL range selector driving the entire dashboard */}
                <div className="flex items-center gap-2">
                    <span className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider hidden sm:inline">Range:</span>
                    <div className="flex rounded-xl p-0.5 border border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]">
                        {["7D", "30D", "90D", "1Y"].map(t => (
                            <button 
                                key={t} 
                                onClick={() => setTimeRange(t)} 
                                className={`px-2.5 py-0.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                                    timeRange === t 
                                        ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-xs border border-[var(--border-inner)]" 
                                        : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] border border-transparent"
                                }`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* ===================================================
                3. Actionable Posture Status Banner (if high-risk / review exist)
            =================================================== */}
            {(fakeProfilesCount > 0 || reviewCount > 0) && (
                <div className={`p-3.5 rounded-xl border ${bannerBorder} ${bannerBg} mb-6 flex flex-wrap items-center justify-between gap-3 text-xs`}>
                    <div className="flex items-center gap-2.5">
                        <AlertTriangle size={15} className={`shrink-0 ${bannerText}`} />
                        <span className="text-[var(--text-primary)] font-medium">
                            <strong className={bannerText}>{bannerPostureLabel} Level</strong> · {formatNumber(fakeProfilesCount)} high-risk profile{fakeProfilesCount === 1 ? "" : "s"} detected in the last {rangeLabel}
                            {reviewCount > 0 ? ` · ${formatNumber(reviewCount)} awaiting review` : ""}
                        </span>
                    </div>
                    <button
                        onClick={() => onNavigate && onNavigate("history")}
                        className="text-xs font-bold text-[var(--accent-light)] hover:underline flex items-center gap-1 cursor-pointer ml-auto"
                    >
                        <span>Review now</span>
                        <ChevronRight size={13} />
                    </button>
                </div>
            )}

            {/* Error Banner with Retry */}
            {error && (
                <div className="bg-[rgba(220,38,38,0.06)] border border-[rgba(220,38,38,0.25)] rounded-2xl p-4 text-[#ef4444] text-xs font-medium mb-6 flex justify-between items-center animate-slide-down">
                    <div className="flex items-center gap-2.5">
                        <AlertTriangle size={16} className="shrink-0 text-[var(--risk-high)]" />
                        <span>{error}</span>
                    </div>
                    <button 
                        className="btn-ghost text-xs py-1 px-3 border border-[rgba(220,38,38,0.3)] rounded-lg font-bold cursor-pointer" 
                        onClick={() => loadDashboardData()}
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* ===================================================
                4. Config-Driven 12-Column Dense Bento Grid
            =================================================== */}
            {visibleWidgets.length > 0 ? (
                <div className={`grid grid-cols-1 lg:grid-cols-12 ${isCompact ? "gap-4" : "gap-6"} [grid-auto-flow:dense]`}>
                    {visibleWidgets.map(id => renderWidget(id))}
                </div>
            ) : (
                /* Empty state when all widgets are hidden */
                <div className="py-16 text-center rounded-2xl border border-[var(--border-inner)] bg-[var(--bg-card)] p-8">
                    <SlidersHorizontal size={36} className="mx-auto mb-3 text-[var(--text-muted)] opacity-50" />
                    <h3 className="text-base font-bold text-[var(--text-primary)]">All dashboard widgets are hidden</h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-1 mb-4">
                        Your custom layout has all sections turned off. Click below to restore the default layout.
                    </p>
                    <button 
                        onClick={() => setPrefs(DEFAULT_PREFS)} 
                        className="px-4 py-2 text-xs font-bold rounded-xl bg-[var(--btn-primary-bg)] text-white shadow-xs cursor-pointer hover:opacity-95"
                    >
                        Restore layout
                    </button>
                </div>
            )}

            {/* Slide-over Customize Drawer Portal */}
            <CustomizeDrawer 
                isOpen={showCustomize}
                onClose={() => {
                    setShowCustomize(false);
                    customizeBtnRef.current?.focus();
                }}
                prefs={prefs}
                setPrefs={setPrefs}
                onReset={() => setPrefs(DEFAULT_PREFS)}
            />

            {/* Keyboard Shortcuts Popover */}
            <ShortcutsPopover 
                isOpen={showShortcuts}
                onClose={() => setShowShortcuts(false)}
            />

        </div>
    );
}
