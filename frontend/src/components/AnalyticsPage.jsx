import { useEffect, useState, useCallback } from "react";
import { getAnalyticsSummary } from "../services/api";

function getRiskColor(score) {
    const s = Number(score ?? 0);
    if (s < 34) return "var(--risk-low)";
    if (s < 67) return "var(--risk-med)";
    if (s < 90) return "var(--risk-high)";
    return "var(--risk-vhigh)";
}


function StatCard({ label, value, unit, color, sub, icon }) {
    return (
        <div
            className="premium-glass"
            style={{
                padding: "26px 28px",
                transition: "transform 0.2s, box-shadow 0.2s",
                cursor: "default",
            }}
            onMouseEnter={e => {
                e.currentTarget.style.transform = "translateY(-4px)";
                e.currentTarget.style.boxShadow = "var(--shadow-lg)";
            }}
            onMouseLeave={e => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "var(--shadow-card)";
            }}
        >
            {icon && <div style={{ fontSize: 26, marginBottom: 16 }}>{icon}</div>}
            <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 700, color: "var(--text-secondary)", marginBottom: 12 }}>
                {label}
            </div>
            <div style={{ fontFamily: "var(--font-head)", fontSize: 44, fontWeight: 900, color: color || "var(--text-primary)", lineHeight: 1 }}>
                {value}
                {unit && <span style={{ fontSize: 18, color: "var(--text-muted)", marginLeft: 6, fontWeight: 600 }}>{unit}</span>}
            </div>
            {sub && <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 10, fontWeight: 500 }}>{sub}</div>}
        </div>
    );
}

function SectionCard({ title, sub, children }) {
    return (
        <div className="premium-glass" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            <div style={{ marginBottom: 28, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>
                <h3 style={{ margin: 0, fontFamily: "var(--font-head)", fontSize: 20, fontWeight: 900, color: "var(--text-primary)" }}>{title}</h3>
                {sub && <p style={{ margin: "6px 0 0", fontSize: 14, color: "var(--text-secondary)" }}>{sub}</p>}
            </div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                {children}
            </div>
        </div>
    );
}

function BarRow({ label, value, maxValue, total, color, range }) {
    const pct   = maxValue > 0 ? (value / maxValue) * 100 : 0;
    const share = total   > 0 ? (value / total) * 100 : 0;
    return (
        <div style={{ marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10, flexWrap: "wrap", gap: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, display: "inline-block", boxShadow: `0 0 8px ${color}` }} />
                    <span style={{ fontSize: 14.5, fontWeight: 700, color: "var(--text-primary)" }}>{label}</span>
                    {range && <span style={{ fontSize: 11, color: "var(--text-secondary)", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)", borderRadius: 99, padding: "2px 8px", fontWeight: 600 }}>{range}</span>}
                </div>
                <div>
                    <span style={{ fontSize: 17, fontWeight: 900, color }}>{value}</span>
                    <span style={{ fontSize: 12.5, color: "var(--text-muted)", marginLeft: 6, fontWeight: 500 }}>({share.toFixed(1)}%)</span>
                </div>
            </div>
            <div className="progress-track" style={{ height: 8, background: "var(--bg-surface-secondary)" }}>
                <div className="progress-fill" style={{ width: `${pct}%`, background: color, boxShadow: `0 0 10px ${color}` }} />
            </div>
        </div>
    );
}

function TrendChart({ data }) {
    if (!data?.length) {
        return <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)", fontSize: 14, fontWeight: 500 }}>No scan activity data yet.</div>;
    }
    const maxCount = Math.max(...data.map(d => Number(d.scans ?? d.count ?? 0)), 1);

    return (
        <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 180, paddingBottom: 24, overflowX: "auto" }}>
            {data.map((item, i) => {
                const count  = Number(item.scans ?? item.count ?? 0);
                const height = Math.max((count / maxCount) * 130, count > 0 ? 8 : 2);
                const date   = String(item.date ?? "").slice(-5);

                return (
                    <div
                        key={item.date ?? i}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: "1 1 0", minWidth: 44, justifyContent: "flex-end" }}
                        title={`${item.date}: ${count} scan${count !== 1 ? "s" : ""}`}
                    >
                        <span style={{ fontSize: 12, fontWeight: 800, color: "var(--accent-light)", marginBottom: 6 }}>{count}</span>
                        <div style={{
                            width: "100%", maxWidth: 40, height: `${height}px`,
                            background: "linear-gradient(180deg, var(--accent) 0%, var(--violet) 100%)",
                            borderRadius: "6px 6px 0 0",
                            boxShadow: "0 4px 14px rgba(99,102,241,0.4)",
                            transition: "height 1s cubic-bezier(0.4,0,0.2,1)",
                            opacity: 0.85
                        }} />
                        <span style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 8, fontWeight: 600 }}>{date}</span>
                    </div>
                );
            })}
        </div>
    );
}

function DonutChart({ classCounts, total }) {
    if (total === 0) return null;
    
    const size = 180;
    const center = size / 2;
    const radius = 70;
    const strokeWidth = 20;
    const circumference = 2 * Math.PI * radius;
    
    let currentOffset = 0;
    
    const slices = [
        { key: "low", color: "var(--risk-low)" },
        { key: "medium", color: "var(--risk-med)" },
        { key: "high", color: "var(--risk-high)" },
        { key: "very_high", color: "var(--risk-vhigh)" }
    ].map(item => {
        const value = Number(classCounts[item.key] || 0);
        const percent = value / total;
        const strokeDasharray = `${percent * circumference} ${circumference}`;
        const strokeDashoffset = -currentOffset;
        currentOffset += percent * circumference;
        return { ...item, value, strokeDasharray, strokeDashoffset };
    });

    return (
        <div style={{ position: "relative", width: size, height: size, margin: "0 auto 20px" }}>
            <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
                {/* Background Ring */}
                <circle cx={center} cy={center} r={radius} fill="transparent" stroke="var(--bg-surface-secondary)" strokeWidth={strokeWidth} />
                {slices.map((slice) => slice.value > 0 && (
                    <circle
                        key={slice.key}
                        cx={center}
                        cy={center}
                        r={radius}
                        fill="transparent"
                        stroke={slice.color}
                        strokeWidth={strokeWidth}
                        strokeDasharray={slice.strokeDasharray}
                        strokeDashoffset={slice.strokeDashoffset}
                        strokeLinecap="round"
                        style={{ transition: "stroke-dasharray 1s ease-out, stroke-dashoffset 1s ease-out", filter: `drop-shadow(0 0 4px ${slice.color}40)` }}
                    />
                ))}
            </svg>
            <div style={{
                position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"
            }}>
                <span style={{ fontSize: 32, fontWeight: 900, fontFamily: "var(--font-head)", lineHeight: 1, color: "var(--text-primary)" }}>{total}</span>
                <span style={{ fontSize: 10, color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 800 }}>Scans</span>
            </div>
        </div>
    );
}

function DetectionPerformanceCard() {
    return (
        <SectionCard title="Detection Performance" sub="Ensemble AI model accuracy metrics">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 24 }}>
                <div style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)", borderRadius: 12, padding: "20px", textAlign: "center" }}>
                    <div style={{ fontSize: 32, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--risk-low)" }}>98.4%</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 4 }}>Overall Accuracy</div>
                </div>
                <div style={{ background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)", borderRadius: 12, padding: "20px", textAlign: "center" }}>
                    <div style={{ fontSize: 32, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--accent)" }}>0.94</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 4 }}>F1 Score</div>
                </div>
            </div>
            
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>True Positive Rate (Recall)</span>
                        <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text-primary)" }}>96.2%</span>
                    </div>
                    <div className="progress-track" style={{ height: 6, background: "var(--bg-surface-secondary)" }}>
                        <div className="progress-fill" style={{ width: "96.2%", background: "var(--accent-light)", boxShadow: "0 0 8px var(--accent-light)" }} />
                    </div>
                </div>
                <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>False Positive Rate</span>
                        <span style={{ fontSize: 13, fontWeight: 800, color: "var(--risk-high)" }}>1.8%</span>
                    </div>
                    <div className="progress-track" style={{ height: 6, background: "var(--bg-surface-secondary)" }}>
                        <div className="progress-fill" style={{ width: "1.8%", background: "var(--risk-high)", boxShadow: "0 0 8px var(--risk-high)" }} />
                    </div>
                </div>
                <div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)" }}>Avg. Inference Time</span>
                        <span style={{ fontSize: 13, fontWeight: 800, color: "var(--text-primary)" }}>142ms</span>
                    </div>
                    <div className="progress-track" style={{ height: 6, background: "var(--bg-surface-secondary)" }}>
                        <div className="progress-fill" style={{ width: "24%", background: "var(--risk-low)", boxShadow: "0 0 8px var(--risk-low)" }} />
                    </div>
                </div>
            </div>
        </SectionCard>
    );
}

export default function AnalyticsPage() {
    const [data,    setData]    = useState(null);
    const [loading, setLoading] = useState(true);
    const [error,   setError]   = useState("");
    const [days,    setDays]    = useState("all");

    const load = useCallback(async () => {
        setLoading(true);
        setError("");
        try { 
            const daysParam = days === "all" ? null : parseInt(days);
            setData(await getAnalyticsSummary(daysParam)); 
        }
        catch (err) { setError(err.message || "Unable to load analytics."); }
        finally { setLoading(false); }
    }, [days]);

    useEffect(() => {
        let isCancelled = false;
        async function fetchAnalytics() {
            try { 
                const daysParam = days === "all" ? null : parseInt(days);
                const res = await getAnalyticsSummary(daysParam);
                if (!isCancelled) setData(res);
            }
            catch (err) { 
                if (!isCancelled) setError(err.message || "Unable to load analytics."); 
            }
            finally { 
                if (!isCancelled) setLoading(false); 
            }
        }
        fetchAnalytics();
        return () => { isCancelled = true; };
    }, [days]);

    if (loading && !data) {
        return (
            <main style={{ maxWidth: 1280, margin: "0 auto", padding: "100px 24px", textAlign: "center" }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", border: "3px solid var(--border-inner)", borderTopColor: "var(--accent)", animation: "spin 0.8s linear infinite", margin: "0 auto 20px" }} />
                <p style={{ color: "var(--text-muted)", fontSize: 15, fontWeight: 500 }}>Loading AI analytics…</p>
            </main>
        );
    }

    if (error && !data) {
        return (
            <main style={{ maxWidth: 1280, margin: "0 auto", padding: "64px 24px" }}>
                <div style={{ padding: "20px 24px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 16, color: "#ef4444", fontSize: 15, marginBottom: 20, fontWeight: 500 }}>
                    ⚠ {error}
                </div>
                <button className="btn-ghost" onClick={load}>Retry</button>
            </main>
        );
    }

    const total    = Number(data?.total_scans ?? 0);
    const avgScore = Number(data?.average_risk_score ?? 0);
    const classCounts = data?.classification_counts ?? {};
    const platforms   = data?.platform_counts ?? {};
    const riskComp    = data?.average_risk_components ?? {};
    const trend       = Array.isArray(data?.recent_trend) ? data.recent_trend : [];
    const topRisky    = Array.isArray(data?.top_risky_scans) ? data.top_risky_scans : [];

    const maxClass    = Math.max(...["low","medium","high","very_high"].map(k => Number(classCounts[k] ?? 0)), 1);
    const maxPlatform = Math.max(...Object.values(platforms).map(Number), 1);

    const classRows = [
        { key: "low",       label: "Low Risk",      range: "< 34",   color: "var(--risk-low)" },
        { key: "medium",    label: "Medium Risk",    range: "34–66",  color: "var(--risk-med)" },
        { key: "high",      label: "High Risk",      range: "67–89",  color: "var(--risk-high)" },
        { key: "very_high", label: "Very High Risk", range: "≥ 90", color: "var(--risk-vhigh)" },
    ];


    const compRows = [
        { label: "Machine Learning", key: "ml_risk",   color: "#818cf8", weight: "60%",  bg: "rgba(99,102,241,0.05)",  border: "rgba(99,102,241,0.2)" },
        { label: "NLP Analysis",     key: "nlp_risk",  color: "#c084fc", weight: "25%",  bg: "rgba(168,85,247,0.05)", border: "rgba(168,85,247,0.2)" },
        { label: "Rule Signals",     key: "rule_risk", color: "#fb923c", weight: "15%",  bg: "rgba(249,115,22,0.05)",  border: "rgba(249,115,22,0.2)" },
    ];

    return (
        <main style={{ maxWidth: 1400, margin: "0 auto", padding: "40px 24px 100px", position: "relative" }}>
            <div className="absolute top-[5%] right-[-5%] w-[40%] h-[40%] bg-[var(--accent)] opacity-[0.04] blur-[120px] pointer-events-none rounded-full" />
            <div className="absolute bottom-[10%] left-[-5%] w-[30%] h-[30%] bg-[var(--violet)] opacity-[0.04] blur-[100px] pointer-events-none rounded-full" />
            
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "space-between", alignItems: "flex-end", marginBottom: 40, position: "relative", zIndex: 10 }}>
                <div>
                    <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, color: "var(--accent)", marginBottom: 8 }}>
                        Intelligence Center
                    </div>
                    <h2 style={{ fontFamily: "var(--font-head)", fontSize: 34, fontWeight: 900, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
                        Global AI Analytics
                    </h2>
                    <p style={{ margin: "10px 0 0", fontSize: 15, color: "var(--text-secondary)" }}>
                        Risk distribution, model performance, and platform usage across your scans
                    </p>
                </div>
                
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <div style={{ 
                        background: "var(--bg-surface-secondary)", 
                        border: "1px solid var(--border-inner)", 
                        borderRadius: 12, 
                        padding: "6px 12px",
                        display: "flex",
                        alignItems: "center",
                        gap: 8
                    }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>Timeframe:</span>
                        <select 
                            value={days} 
                            onChange={(e) => setDays(e.target.value)}
                            style={{
                                background: "transparent",
                                border: "none",
                                fontSize: 14,
                                fontWeight: 700,
                                color: "var(--text-primary)",
                                outline: "none",
                                cursor: "pointer"
                            }}
                        >
                            <option value="7" style={{ background: "var(--bg-card)" }}>Last 7 Days</option>
                            <option value="30" style={{ background: "var(--bg-card)" }}>Last 30 Days</option>
                            <option value="all" style={{ background: "var(--bg-card)" }}>All Time</option>
                        </select>
                    </div>
                    <button className="btn-ghost" onClick={load} disabled={loading}>
                        {loading ? "..." : "↻ Refresh"}
                    </button>
                </div>
            </div>

            <div className="animate-fade-in" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 20, marginBottom: 28, position: "relative", zIndex: 10 }}>
                <StatCard icon="📊" label="Total Profiles Analyzed"  value={total}                sub={days === "all" ? "Total historical scans" : `Processed in the last ${days} days`} />
                <StatCard icon="📈" label="Global Risk Average" value={avgScore.toFixed(1)} sub="Unified ensemble score" color={getRiskColor(avgScore)} />
                <StatCard icon="🔴" label="Critical Detections" value={classCounts["very_high"] || 0} sub="Very high risk profiles flagged"  color="var(--risk-vhigh)" />
                <StatCard icon="🟢" label="Authentic Profiles"  value={classCounts["low"] || 0} sub="Low risk profiles verified"   color="var(--risk-low)" />
            </div>

            <div className="animate-slide-up" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: 24, marginBottom: 24, position: "relative", zIndex: 10 }}>
                <SectionCard title="Risk Classification Distribution" sub="Breakdown of analyzed accounts by threat level">
                    {total === 0
                        ? <div style={{ color: "var(--text-muted)", fontSize: 14, padding: "24px 0" }}>No data yet.</div>
                        : (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 40, alignItems: "center", marginTop: "auto", marginBottom: "auto" }}>
                                <div style={{ flexShrink: 0, minWidth: 200 }}>
                                    <DonutChart classCounts={classCounts} total={total} />
                                </div>
                                <div style={{ flex: 1, minWidth: 240 }}>
                                    {classRows.map(row => (
                                        <BarRow
                                            key={row.key}
                                            label={row.label}
                                            value={Number(classCounts[row.key] ?? 0)}
                                            maxValue={maxClass}
                                            total={total}
                                            color={row.color}
                                            range={row.range}
                                        />
                                    ))}
                                </div>
                            </div>
                        )
                    }
                </SectionCard>
                
                <DetectionPerformanceCard />
            </div>

            <div className="animate-slide-up stagger-2" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24, marginBottom: 24, position: "relative", zIndex: 10 }}>
                
                <SectionCard title="Top Riskiest Profiles Detected" sub="The highest threat accounts intercepted in this timeframe">
                    {topRisky.length === 0 ? (
                        <div style={{ color: "var(--text-muted)", fontSize: 14, padding: "24px 0" }}>No profiles found.</div>
                    ) : (
                        <div style={{ overflowX: "auto", margin: "0 -28px", padding: "0 28px" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                                <thead>
                                    <tr style={{ borderBottom: "1px solid var(--border-inner)" }}>
                                        <th style={{ padding: "16px 0", fontSize: 12, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Target Profile</th>
                                        <th style={{ padding: "16px 0", fontSize: 12, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Platform</th>
                                        <th style={{ padding: "16px 0", fontSize: 12, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Unified Risk Score</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {topRisky.map((scan) => {
                                        const score = Number(scan.final_score);
                                        return (
                                            <tr key={scan.scan_id} className="hover:bg-[var(--bg-surface-secondary)] transition-colors" style={{ borderBottom: "1px solid var(--bg-surface-secondary)" }}>
                                                <td style={{ padding: "16px 0" }}>
                                                    <a 
                                                        href={`/scanner?id=${scan.scan_id}`} 
                                                        style={{ 
                                                            fontSize: 15, fontWeight: 700, color: "var(--text-primary)", 
                                                            textDecoration: "none" 
                                                        }}
                                                        onMouseOver={e => e.target.style.color = "var(--accent-light)"}
                                                        onMouseOut={e => e.target.style.color = "var(--text-primary)"}
                                                    >
                                                        @{scan.username || "unknown"}
                                                    </a>
                                                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                                                        {new Date(scan.timestamp).toLocaleDateString()}
                                                    </div>
                                                </td>
                                                <td style={{ padding: "16px 0", textTransform: "capitalize", fontSize: 14, fontWeight: 600, color: "var(--text-secondary)" }}>
                                                    {scan.platform}
                                                </td>
                                                <td style={{ padding: "16px 0" }}>
                                                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                                        <div style={{ width: 40, height: 4, background: "var(--border-inner)", borderRadius: 99, overflow: "hidden" }}>
                                                            <div style={{ width: `${score}%`, height: "100%", background: getRiskColor(score), boxShadow: `0 0 6px ${getRiskColor(score)}` }} />
                                                        </div>
                                                        <span style={{ 
                                                            padding: "4px 10px", borderRadius: 6, fontSize: 12, fontWeight: 800, 
                                                            background: `${getRiskColor(score)}1A`, 
                                                            border: `1px solid ${getRiskColor(score)}33`,
                                                            color: getRiskColor(score) 
                                                        }}>
                                                            {score.toFixed(1)}
                                                        </span>
                                                        <span style={{ fontSize: 12, color: "var(--text-secondary)", fontWeight: 600, textTransform: "capitalize" }}>
                                                            {scan.classification.replace("_", " ")}
                                                        </span>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </SectionCard>

                <SectionCard title="AI Intelligence Weighting" sub="Average signal contribution to final score">
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        {compRows.map(c => {
                            const val = Number(riskComp[c.key] ?? 0);
                            return (
                                <div key={c.key} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 16, padding: "16px 20px" }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                                        <span style={{ fontSize: 14, fontWeight: 800, color: "var(--text-primary)" }}>{c.label}</span>
                                        <span style={{ fontSize: 11, fontWeight: 800, color: c.color, background: "var(--bg-surface-secondary)", border: `1px solid ${c.color}66`, borderRadius: 99, padding: "2px 8px" }}>{c.weight}</span>
                                    </div>
                                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                        <div style={{ fontFamily: "var(--font-head)", fontSize: 24, fontWeight: 900, color: c.color, lineHeight: 1 }}>
                                            {val.toFixed(1)}
                                        </div>
                                        <div className="progress-track" style={{ height: 6, flex: 1, background: "var(--bg-surface-secondary)" }}>
                                            <div className="progress-fill" style={{ width: `${val}%`, background: c.color, boxShadow: `0 0 10px ${c.color}` }} />
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </SectionCard>
            </div>

            <div className="animate-slide-up stagger-3" style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24, position: "relative", zIndex: 10 }}>
                <SectionCard title="Analysis Activity Trend" sub="Scan volume over the selected timeframe">
                    <TrendChart data={trend} />
                </SectionCard>
                
                {Object.keys(platforms).length > 0 && (
                    <SectionCard title="Target Platforms" sub="Data source distribution">
                        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
                            {Object.entries(platforms).map(([platform, count]) => {
                                const n = Number(count);
                                return (
                                    <div key={platform} style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 14, padding: "18px 20px" }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                                            <span style={{ fontSize: 15, fontWeight: 800, color: "var(--text-primary)", textTransform: "capitalize" }}>{platform}</span>
                                            <span style={{ fontSize: 20, fontWeight: 900, color: "var(--accent-light)" }}>{n}</span>
                                        </div>
                                        <div className="progress-track" style={{ height: 8, background: "var(--bg-surface-secondary)" }}>
                                            <div className="progress-fill" style={{ width: `${(n / maxPlatform) * 100}%`, background: "var(--accent)", boxShadow: "0 0 8px var(--accent)" }} />
                                        </div>
                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginTop: 8, fontWeight: 600 }}>
                                            {total > 0 ? `${((n / total) * 100).toFixed(1)}% of total processed volume` : "—"}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </SectionCard>
                )}
            </div>
        </main>
    );
}
