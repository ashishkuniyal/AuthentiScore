import { useEffect, useState, Fragment } from "react";
import { getScanHistory, downloadReportPdf } from "../services/api";
import { Filter, Download, ChevronDown } from "lucide-react";
import { getRiskBand } from "../utils/risk";

function getRiskColor(score) {
    const band = getRiskBand(score);
    if (band.key === "low") return "var(--risk-low)";
    if (band.key === "medium") return "var(--risk-med)";
    if (band.key === "high") return "var(--risk-high)";
    return "var(--risk-vhigh)";
}

function getRiskLabel(score) {
    return getRiskBand(score).label;
}

function getRiskBadgeStyle(score) {
    const band = getRiskBand(score);
    if (band.key === "low") return { background: "rgba(16,185,129,0.1)",  color: "var(--risk-low)", border: "1px solid rgba(16,185,129,0.2)" };
    if (band.key === "medium") return { background: "rgba(245,158,11,0.1)",  color: "var(--risk-med)", border: "1px solid rgba(245,158,11,0.2)" };
    if (band.key === "high") return { background: "rgba(239,68,68,0.1)",  color: "var(--risk-high)", border: "1px solid rgba(239,68,68,0.2)" };
    return             { background: "rgba(168,85,247,0.1)",  color: "var(--risk-vhigh)", border: "1px solid rgba(168,85,247,0.2)" };
}

function formatDate(ts) {
    if (!ts) return "N/A";
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "N/A";
    return d.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

function MiniBar({ value = 0 }) {
    return (
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 120 }}>
            <div style={{ flex: 1, height: 6, borderRadius: 99, background: "var(--border-inner)", overflow: "hidden" }}>
                <div className="progress-fill" style={{ width: `${Math.min(value, 100)}%`, background: getRiskColor(value), height: "100%", borderRadius: 99, boxShadow: `0 0 10px ${getRiskColor(value)}` }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 800, color: getRiskColor(value), minWidth: 36, textAlign: "right" }}>
                {Number(value).toFixed(1)}
            </span>
        </div>
    );
}

function PdfDownloadButton({ scanId }) {
    const [downloading, setDownloading] = useState(false);

    const handleDownload = async () => {
        if (!scanId || downloading) return;
        setDownloading(true);
        try {
            const blob = await downloadReportPdf(scanId);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `authentiscore_report_${scanId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => {
                URL.revokeObjectURL(url);
            }, 1000);
        } catch (err) {
            alert(err.message || "Download failed");
        } finally {
            setDownloading(false);
        }
    };

    return (
        <button
            onClick={handleDownload}
            disabled={downloading}
            style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "8px 16px",
                background: "rgba(16, 185, 129, 0.1)",
                color: "#10b981",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                borderRadius: 8,
                cursor: downloading ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 700,
                transition: "all 0.2s"
            }}
            onMouseOver={e => e.currentTarget.style.background = "rgba(16, 185, 129, 0.2)"}
            onMouseOut={e => e.currentTarget.style.background = "rgba(16, 185, 129, 0.1)"}
        >
            <Download size={14} /> {downloading ? "Downloading..." : "Download PDF Report"}
        </button>
    );
}

function ExpandedRow({ scan }) {
    const rc = scan.risk_components ?? {};
    return (
        <tr className="animate-fade-in">
            <td colSpan={6} style={{ padding: "0 24px 24px", background: "var(--bg-surface-secondary)", borderBottom: "1px solid var(--border-inner)" }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, paddingTop: 16 }}>
                    {[
                        { label: "ML Risk",   value: rc.ml_risk },
                        { label: "NLP Risk",  value: rc.nlp_risk },
                        { label: "Rule Risk", value: rc.rule_risk },
                    ].map(item => (
                        <div key={item.label} style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 12, padding: "14px 16px", boxShadow: "inset 0 1px 0 var(--bg-surface-secondary)" }}>
                            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-secondary)", fontWeight: 700, marginBottom: 10 }}>{item.label}</div>
                            <MiniBar value={Number(item.value ?? 0)} />
                        </div>
                    ))}
                    {scan.model_name && (
                        <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 12, padding: "14px 16px" }}>
                            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-secondary)", fontWeight: 700, marginBottom: 6 }}>Model</div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>{scan.model_name}</div>
                            {scan.model_version && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{scan.model_version}</div>}
                        </div>
                    )}
                    {scan.scan_id && (
                        <div style={{ background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 12, padding: "14px 16px" }}>
                            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-secondary)", fontWeight: 700, marginBottom: 6 }}>Scan ID</div>
                            <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-secondary)", wordBreak: "break-all" }}>{scan.scan_id}</div>
                        </div>
                    )}
                </div>
                
                {scan.scan_id && (
                    <div style={{ marginTop: 24, textAlign: "right" }}>
                        <PdfDownloadButton scanId={scan.scan_id} />
                    </div>
                )}
            </td>
        </tr>
    );
}

export default function HistoryPage() {
    const [history,  setHistory]  = useState([]);
    const [loading,  setLoading]  = useState(true);
    const [error,    setError]    = useState("");
    const [search,   setSearch]   = useState("");
    const [filter,   setFilter]   = useState("all");
    const [sortKey,  setSortKey]  = useState("timestamp");
    const [sortAsc,  setSortAsc]  = useState(false);
    const [expanded, setExpanded] = useState(null);

    useEffect(() => {
        let isCancelled = false;
        async function fetchHistory() {
            try { 
                const data = await getScanHistory();
                if (!isCancelled) setHistory(Array.isArray(data) ? data : []); 
            }
            catch (err) { if (!isCancelled) setError(err.message || "Unable to load history."); }
            finally { if (!isCancelled) setLoading(false); }
        }
        fetchHistory();
        return () => { isCancelled = true; };
    }, []);


    function toggleSort(key) {
        if (sortKey === key) setSortAsc(a => !a);
        else { setSortKey(key); setSortAsc(false); }
    }

    const filtered = history
        .filter(s => {
            if (!search && filter === "all") return true;
            let matchSearch = true;
            let matchFilter = true;
            
            if (search) {
                const q = search.toLowerCase();
                matchSearch = (s.username ?? "").toLowerCase().includes(q) ||
                              (s.platform ?? "").toLowerCase().includes(q) ||
                              (s.profile_url ?? "").toLowerCase().includes(q);
            }
            
            if (filter === "instagram") matchFilter = (s.platform ?? "").toLowerCase() === "instagram";
            if (filter === "twitter") matchFilter = (s.platform ?? "").toLowerCase() === "twitter" || (s.platform ?? "").toLowerCase() === "x";
            if (filter === "high_risk") matchFilter = Number(s.final_score ?? 0) >= 67;
            if (filter === "low_risk") matchFilter = Number(s.final_score ?? 0) < 34;
            
            return matchSearch && matchFilter;
        })
        .sort((a, b) => {
            if (sortKey === "final_score") {
                const av = Number(a.final_score ?? 0), bv = Number(b.final_score ?? 0);
                return sortAsc ? av - bv : bv - av;
            }
            if (sortKey === "timestamp") {
                const av = new Date(a.timestamp || 0).getTime(), bv = new Date(b.timestamp || 0).getTime();
                return sortAsc ? av - bv : bv - av;
            }
            const av = String(a[sortKey] ?? ""), bv = String(b[sortKey] ?? "");
            return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        });

    const COLS = [
        { key: "username",    label: "Profile",    sortable: true },
        { key: "platform",    label: "Platform",   sortable: true },
        { key: "final_score", label: "Risk Score", sortable: true },
        { key: "classification", label: "Level",   sortable: false },
        { key: "timestamp",   label: "Scanned At",    sortable: true },
        { key: "_expand",     label: "",           sortable: false },
    ];

    const FILTERS = [
        { id: "all", label: "All Records" },
        { id: "instagram", label: "Instagram Only" },
        { id: "twitter", label: "Twitter Only" },
        { id: "high_risk", label: "High Risk (>= 67)" },
        { id: "low_risk", label: "Low Risk (< 34)" },
    ];


    return (
        <main style={{ maxWidth: 1400, margin: "0 auto", padding: "40px 24px 100px", position: "relative" }}>
            <div className="absolute top-[-10%] right-[-5%] w-[40%] h-[40%] bg-[var(--accent)] opacity-[0.03] blur-[120px] pointer-events-none rounded-full" />
            
            <div style={{ display: "flex", flexWrap: "wrap", gap: 16, justifyContent: "space-between", alignItems: "flex-end", marginBottom: 24, position: "relative", zIndex: 10 }}>
                <div>
                    <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, color: "var(--accent)", marginBottom: 8 }}>
                        Scan History
                    </div>
                    <h2 style={{ fontFamily: "var(--font-head)", fontSize: 34, fontWeight: 900, color: "var(--text-primary)", margin: 0, letterSpacing: "-0.02em" }}>
                        Analysis Log
                    </h2>
                    <p style={{ margin: "10px 0 0", fontSize: 15, color: "var(--text-secondary)" }}>
                        {history.length} total scan{history.length !== 1 ? "s" : ""} securely stored in AuthentiScore.
                    </p>
                </div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                    <div style={{ position: "relative" }}>
                        <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)" }}>🔍</span>
                        <input
                            type="search"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Search username, platform…"
                            className="input-field"
                            style={{ width: 280, paddingLeft: 40, background: "var(--bg-surface-secondary)" }}
                        />
                    </div>
                    <button className="btn-ghost" onClick={load} disabled={loading}>
                        {loading ? "Loading…" : "↻ Refresh"}
                    </button>
                </div>
            </div>

            {/* Global Filter System */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24, overflowX: "auto", paddingBottom: 8, position: "relative", zIndex: 10 }} className="scrollbar-hide">
                <Filter size={16} color="var(--text-muted)" style={{ marginRight: 8 }} />
                {FILTERS.map(f => (
                    <button
                        key={f.id}
                        onClick={() => setFilter(f.id)}
                        style={{
                            padding: "6px 14px",
                            borderRadius: 99,
                            fontSize: 13,
                            fontWeight: 600,
                            border: filter === f.id ? "1px solid var(--accent)" : "1px solid var(--border-inner)",
                            background: filter === f.id ? "rgba(99,102,241,0.15)" : "var(--bg-surface-secondary)",
                            color: filter === f.id ? "var(--accent-light)" : "var(--text-secondary)",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            whiteSpace: "nowrap"
                        }}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {error && (
                <div style={{ padding: "16px 20px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 14, color: "#b91c1c", fontSize: 14.5, marginBottom: 24, fontWeight: 500 }}>
                    ⚠ {error}
                </div>
            )}

            {loading && (
                <div style={{ padding: 80, textAlign: "center" }}>
                    <div style={{ width: 38, height: 38, borderRadius: "50%", border: "3px solid var(--border-inner)", borderTopColor: "var(--accent)", animation: "spin 0.8s linear infinite", margin: "0 auto 18px" }} />
                    <p style={{ color: "var(--text-muted)", fontSize: 15, fontWeight: 500 }}>Loading scan history…</p>
                </div>
            )}

            {!loading && filtered.length === 0 && (
                <div className="premium-glass" style={{ padding: "64px 24px", textAlign: "center" }}>
                    <div style={{ fontSize: 44, marginBottom: 20, opacity: 0.5 }}>◷</div>
                    <div style={{ fontFamily: "var(--font-head)", fontSize: 20, fontWeight: 800, color: "var(--text-primary)", marginBottom: 8 }}>
                        {search || filter !== "all" ? "No results match your filters" : "No scans yet"}
                    </div>
                    <p style={{ color: "var(--text-secondary)", fontSize: 14.5, margin: 0 }}>
                        {search || filter !== "all" ? "Try adjusting your search or filter settings." : "Complete a profile scan and it will appear here."}
                    </p>
                    {(search || filter !== "all") && (
                        <button className="btn-ghost mt-6" onClick={() => { setSearch(""); setFilter("all"); }}>
                            Clear Filters
                        </button>
                    )}
                </div>
            )}

            {!loading && filtered.length > 0 && (
                <div className="premium-glass" style={{ padding: 0, overflow: "hidden", position: "relative", zIndex: 10 }}>
                    <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
                            <thead>
                                <tr style={{ borderBottom: "1px solid var(--border-inner)", background: "var(--bg-surface-secondary)" }}>
                                    {COLS.map(col => (
                                        <th
                                            key={col.key}
                                            onClick={col.sortable ? () => toggleSort(col.key) : undefined}
                                            style={{
                                                padding: "16px 24px", textAlign: "left",
                                                fontSize: 11.5, fontWeight: 800,
                                                textTransform: "uppercase", letterSpacing: "0.08em",
                                                color: sortKey === col.key ? "var(--accent-light)" : "var(--text-muted)",
                                                cursor: col.sortable ? "pointer" : "default",
                                                whiteSpace: "nowrap", userSelect: "none",
                                                transition: "color 0.2s",
                                            }}
                                        >
                                            {col.label}
                                            {col.sortable && (
                                                <span style={{ marginLeft: 6, opacity: sortKey === col.key ? 1 : 0.3 }}>
                                                    {sortKey === col.key ? (sortAsc ? "↑" : "↓") : "↕"}
                                                </span>
                                            )}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map((scan, idx) => {
                                    const score = Number(scan.final_score ?? 0);
                                    const badge = getRiskBadgeStyle(score);
                                    const isOpen = expanded === idx;

                                    return (
                                        <Fragment key={scan.scan_id ?? idx}>
                                            <tr
                                                className="group hover:bg-[var(--bg-surface-secondary)] transition-colors"
                                                style={{
                                                    borderBottom: isOpen ? "none" : "1px solid var(--border-inner)",
                                                    background: isOpen ? "var(--bg-surface-secondary)" : "transparent",
                                                    cursor: "pointer",
                                                }}
                                                onClick={() => setExpanded(isOpen ? null : idx)}
                                            >
                                                <td style={{ padding: "18px 24px" }}>
                                                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                                        <div className="w-8 h-8 rounded-full bg-[var(--bg-surface-secondary)] flex items-center justify-center border border-[var(--bg-surface-secondary)] text-[11px] font-bold shrink-0">
                                                            {scan.platform?.charAt(0) || '@'}
                                                        </div>
                                                        <div>
                                                            <div style={{ fontWeight: 800, color: "var(--text-primary)", fontSize: 14.5, transition: "color 0.2s" }} className="group-hover:text-[var(--accent-light)]">@{scan.username ?? "Unknown"}</div>
                                                            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{scan.profile_url ?? ""}</div>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td style={{ padding: "18px 24px" }}>
                                                    <span style={{ padding: "5px 12px", borderRadius: 99, fontSize: 12.5, fontWeight: 700, background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)", color: "var(--text-secondary)", textTransform: "capitalize" }}>
                                                        {scan.platform ?? "Unknown"}
                                                    </span>
                                                </td>
                                                <td style={{ padding: "18px 24px", minWidth: 150 }}>
                                                    <MiniBar value={score} />
                                                </td>
                                                <td style={{ padding: "18px 24px" }}>
                                                    <span style={{ padding: "5px 12px", borderRadius: 99, fontSize: 12.5, fontWeight: 800, ...badge }}>
                                                        {getRiskLabel(score)}
                                                    </span>
                                                </td>
                                                <td style={{ padding: "18px 24px", fontSize: 13.5, color: "var(--text-secondary)", whiteSpace: "nowrap", fontWeight: 500 }}>
                                                    {formatDate(scan.timestamp)}
                                                </td>
                                                <td style={{ padding: "18px 16px 18px 8px", textAlign: "right" }}>
                                                    <span style={{ color: "var(--text-muted)", fontSize: 14, display: "inline-block", transition: "transform 0.2s", transform: isOpen ? "rotate(180deg)" : "none" }}>
                                                        <ChevronDown size={18} />
                                                    </span>
                                                </td>
                                            </tr>
                                            {isOpen && <ExpandedRow scan={scan} />}
                                        </Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </main>
    );
}
