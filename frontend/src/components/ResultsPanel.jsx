// ResultsPanel.jsx — Enterprise-grade results report
// Layout: Top (Profile + Score Ring) → Middle (Breakdown + Signals) → Bottom (Details + Export)
import { useState } from "react";
import {
    Flag, ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2,
    XCircle, Info, Users, UserCheck, FileText, ImageIcon, Lock,
    ExternalLink, Download, Bot, Activity, Zap, Target,
} from "lucide-react";
import RiskGauge from "./RiskGauge";

const API_BASE_URL = "http://127.0.0.1:8000";

// ─────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────

function clamp(v) { return Math.min(Math.max(Number(v) || 0, 0), 100); }

function fmtNum(v) {
    if (v === null || v === undefined) return "N/A";
    return Number(v).toLocaleString();
}

function getRiskColor(score) {
    const s = clamp(score);
    if (s < 34)  return { text: "#10b981", bg: "rgba(16,185,129,0.12)",  border: "rgba(16,185,129,0.3)"  };
    if (s < 67)  return { text: "#f59e0b", bg: "rgba(245,158,11,0.12)",  border: "rgba(245,158,11,0.3)"  };
    if (s < 90)  return { text: "#f97316", bg: "rgba(249,115,22,0.12)",  border: "rgba(249,115,22,0.3)"  };
    return           { text: "#ef4444", bg: "rgba(239,68,68,0.12)",   border: "rgba(239,68,68,0.3)"   };
}

function getRiskLabel(score) {
    const s = clamp(score);
    if (s < 34) return "Low Risk";
    if (s < 67) return "Medium Risk";
    if (s < 90) return "High Risk";
    return "Very High Risk";
}

/** Detect self-declared automation in the bio. */
function isDeclaredBot(bio = "") {
    const b = (bio || "").toLowerCase();
    return /\b(a bot for|official bot|automated account|this is a bot|bot account|automated by)\b/.test(b);
}

/** Normalize bio: convert literal \n escape sequences → real newlines. */
function normalizeBio(bio) {
    if (!bio) return "";
    // Twitter scraper may store "\n" as a two-character string
    return bio.replace(/\\n/g, "\n").replace(/\\r/g, "").trim();
}

/** Render bio text with clickable URLs. Returns an array of React nodes. */
function renderBioWithLinks(bio) {
    if (!bio) return null;
    const urlRegex = /(https?:\/\/\S+)/g;
    const parts = bio.split(urlRegex);
    return parts.map((part, i) =>
        urlRegex.test(part)
            ? <a key={i} href={part} target="_blank" rel="noreferrer"
                 style={{ color: "var(--accent-light)", textDecoration: "underline", wordBreak: "break-all" }}>{part}</a>
            : <span key={i}>{part}</span>
    );
}

// ─────────────────────────────────────────────────────────────
// Shared card wrapper
// ─────────────────────────────────────────────────────────────

function Card({ children, style = {} }) {
    return (
        <div style={{
            padding: "24px",
            borderRadius: "16px",
            border: "1px solid var(--border-inner)",
            background: "var(--bg-surface-secondary)",
            backdropFilter: "blur(8px)",
            ...style,
        }}>
            {children}
        </div>
    );
}

function CardLabel({ children }) {
    return (
        <div style={{
            fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase", color: "var(--text-secondary)",
            marginBottom: 16,
        }}>
            {children}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Stat chip (followers / following / posts etc.)
// ─────────────────────────────────────────────────────────────

function StatChip({ icon: Icon, label, value, accent }) {
    return (
        <div style={{
            display: "flex", alignItems: "center", gap: 12,
            padding: "14px 16px", borderRadius: 12,
            background: "var(--bg-surface-secondary)",
            border: "1px solid var(--border-inner)",
        }}>
            <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: accent ? `color-mix(in srgb, ${accent} 12%, transparent)` : "rgba(99,102,241,0.12)",
                border: `1px solid ${accent ? `color-mix(in srgb, ${accent} 25%, transparent)` : "rgba(99,102,241,0.2)"}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: accent || "var(--accent-light)",
            }}>
                {Icon && <Icon size={18} />}
            </div>
            <div>
                <div style={{ fontSize: 11, color: "var(--text-secondary)", fontWeight: 600, marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 17, fontWeight: 800, color: "var(--text-primary)", fontFamily: "var(--font-head)" }}>{value}</div>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 1: Executive Summary (profile + ring)
// ─────────────────────────────────────────────────────────────

function ExecutiveSummary({ result }) {
    const profile    = result?.profile ?? {};
    const username   = profile.username ?? result?.username ?? "Unknown";
    const platform   = profile.platform ?? result?.platform ?? "Unknown";
    const url        = profile.profile_url ?? result?.profile_url ?? "";
    const bio        = normalizeBio(profile.bio ?? result?.collected_bio ?? "");
    const status     = profile.collection_status;
    const score      = clamp(result?.final_score ?? 0);
    const breakdown  = result?.score_breakdown ?? {};
    const sigUsed    = breakdown.signals_used ?? 3;
    const nlpInsuff  = breakdown.nlp_insufficient ?? false;
    const botDeclared = isDeclaredBot(bio);
    const riskColor  = getRiskColor(score);
    const riskLabel  = getRiskLabel(score);

    // Verdict sentence
    let verdict = "";
    if (score < 34)      verdict = "This profile shows no significant indicators of inauthenticity.";
    else if (score < 67) verdict = "Some suspicious signals detected. Review the breakdown below.";
    else if (score < 90) verdict = "Multiple strong risk signals detected. High probability of inauthentic activity.";
    else                 verdict = "Critical risk indicators detected. Very likely inauthentic or automated.";
    if (botDeclared)     verdict = "Self-declared automated account. Risk level reflects its behavioral signals.";

    const avatarGrads = [
        "linear-gradient(135deg,#4338ca,#8b5cf6)",
        "linear-gradient(135deg,#0ea5e9,#6366f1)",
        "linear-gradient(135deg,#059669,#0ea5e9)",
        "linear-gradient(135deg,#ea580c,#ef4444)",
    ];
    const avatarGrad = avatarGrads[(username.charCodeAt(0) || 0) % avatarGrads.length];

    return (
        /* two-column on lg+, single column on mobile */
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 20 }}
             className="results-grid-top">
            {/* Left — Profile card */}
            <Card>
                <CardLabel>Profile Overview</CardLabel>

                {/* Avatar + Handle row */}
                <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
                    <div style={{
                        width: 64, height: 64, borderRadius: 16, flexShrink: 0,
                        background: avatarGrad,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 26, fontWeight: 900, color: "var(--text-primary)",
                        fontFamily: "var(--font-head)",
                        boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
                    }}>
                        {username[0]?.toUpperCase() ?? "?"}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                            fontFamily: "var(--font-head)", fontSize: 24, fontWeight: 900,
                            color: "var(--text-primary)", lineHeight: 1.1, letterSpacing: "-0.02em",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}>
                            @{username}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                            <span style={{ fontSize: 13, color: "var(--text-secondary)", textTransform: "capitalize", fontWeight: 600 }}>
                                {platform} Profile
                            </span>
                            {status && (
                                <span style={{
                                    display: "inline-flex", alignItems: "center", gap: 5,
                                    padding: "2px 10px", borderRadius: 99, fontSize: 11, fontWeight: 700,
                                    background: status === "success" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                                    color: status === "success" ? "var(--risk-low)" : "var(--risk-med)",
                                    border: `1px solid ${status === "success" ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}`,
                                }}>
                                    <CheckCircle2 size={12} />
                                    {status === "success" ? "Data verified" : "Manual entry"}
                                </span>
                            )}
                            {botDeclared && (
                                <span style={{
                                    display: "inline-flex", alignItems: "center", gap: 5,
                                    padding: "2px 10px", borderRadius: 99, fontSize: 11, fontWeight: 700,
                                    background: "rgba(99,102,241,0.12)", color: "var(--accent-light)",
                                    border: "1px solid rgba(99,102,241,0.25)",
                                }}>
                                    <Bot size={12} />
                                    Automated (declared)
                                </span>
                            )}
                        </div>
                    </div>
                    {url && (
                        <a href={url} target="_blank" rel="noreferrer" style={{
                            display: "flex", alignItems: "center", gap: 6,
                            padding: "8px 14px", borderRadius: 10, fontSize: 13, fontWeight: 600,
                            color: "var(--text-secondary)", textDecoration: "none",
                            border: "1px solid var(--border-inner)",
                            background: "var(--bg-surface-secondary)",
                            whiteSpace: "nowrap", flexShrink: 0,
                            transition: "color 0.15s, border-color 0.15s",
                        }}
                        onMouseEnter={e => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.borderColor = "var(--border-hover)"; }}
                        onMouseLeave={e => { e.currentTarget.style.color = "var(--text-secondary)"; e.currentTarget.style.borderColor = "var(--border-inner)"; }}>
                            View profile <ExternalLink size={14} />
                        </a>
                    )}
                </div>

                {/* Stats grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginBottom: 20 }}>
                    <StatChip icon={Users}     label="Followers"  value={fmtNum(profile.followers)} />
                    <StatChip icon={UserCheck} label="Following"  value={fmtNum(profile.following)} />
                    <StatChip icon={FileText}  label="Posts"      value={fmtNum(profile.posts)} />
                    <StatChip icon={ImageIcon} label="Avatar"
                        value={profile.has_profile_picture ? "Set" : "Missing"}
                        accent={profile.has_profile_picture ? "var(--risk-low)" : "var(--risk-high)"} />
                    <StatChip icon={Lock}      label="Privacy"    value={profile.is_private ? "Private" : "Public"} />
                </div>

                {/* Bio */}
                {bio?.trim() && (
                    <div style={{
                        background: "var(--bg-surface-secondary)",
                        border: "1px solid var(--border-inner)",
                        borderRadius: 12, padding: "14px 16px",
                    }}>
                        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 8 }}>
                            Bio
                        </div>
                        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                            {renderBioWithLinks(bio)}
                        </p>
                    </div>
                )}
            </Card>

            {/* Right — Risk score ring */}
            <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
                <CardLabel>Unified Risk Score</CardLabel>

                <RiskGauge score={score} animated />

                {/* Declared bot badge alongside risk badge */}
                {botDeclared && (
                    <span style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        padding: "5px 14px", borderRadius: 99, fontSize: 12, fontWeight: 700,
                        background: "rgba(99,102,241,0.12)", color: "var(--accent-light)",
                        border: "1px solid rgba(99,102,241,0.3)",
                    }}>
                        <Bot size={13} /> Automated (declared)
                    </span>
                )}

                {/* Verdict */}
                <p style={{
                    margin: 0, fontSize: 13.5, lineHeight: 1.6, textAlign: "center",
                    color: "var(--text-secondary)", maxWidth: 300,
                }}>
                    {verdict}
                </p>

                {/* Signals used note */}
                {nlpInsuff && (
                    <div style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        padding: "5px 12px", borderRadius: 99, fontSize: 12, fontWeight: 600,
                        background: "var(--bg-surface-secondary)",
                        border: "1px solid var(--border-inner)",
                        color: "var(--text-secondary)",
                    }}>
                        <Info size={13} />
                        Based on {sigUsed} of 3 signals
                    </div>
                )}
            </Card>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 2: Risk Breakdown
// ─────────────────────────────────────────────────────────────

function RiskBreakdown({ result }) {
    const breakdown    = result?.score_breakdown ?? {};
    const components   = breakdown.components ?? {};
    const nlpInsuff    = breakdown.nlp_insufficient ?? false;
    const nlpSignals   = result?.nlp_signals ?? {};
    const semanticExp  = nlpSignals.semantic_explanation ?? "";
    const mlFactors    = result?.top_ml_factors ?? [];

    const bars = [
        {
            key: "ml", label: "Machine Learning", icon: Zap,
            color: "#818cf8",
        },
        {
            key: "nlp", label: "Bio & Text Analysis", icon: Target,
            color: "#a78bfa",
            skip: nlpInsuff,
        },
        {
            key: "rules", label: "Rule Signals", icon: ShieldAlert,
            color: "#f97316",
        },
    ];

    const redFlags    = mlFactors.filter(f => f.is_risk).slice(0, 5);
    const trustSigs   = mlFactors.filter(f => !f.is_risk).slice(0, 5);
    const ruleSignals = result?.rule_signals ?? [];

    return (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 20 }}
             className="results-grid-mid">

            {/* Left — Component bars + NLP card */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <Card>
                    <CardLabel>Risk Breakdown</CardLabel>
                    <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
                        {bars.map(b => {
                            const comp = components[b.key] ?? {};
                            return (
                                <div key={b.key}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                            <div style={{
                                                width: 30, height: 30, borderRadius: 8,
                                                background: `color-mix(in srgb, ${b.color} 14%, transparent)`,
                                                display: "flex", alignItems: "center", justifyContent: "center",
                                                color: b.color, flexShrink: 0,
                                            }}>
                                                <b.icon size={16} />
                                            </div>
                                            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>{b.label}</span>
                                            <span style={{
                                                fontSize: 11, fontWeight: 700,
                                                padding: "2px 8px", borderRadius: 99,
                                                background: "var(--border-inner)",
                                                color: "var(--text-secondary)",
                                            }}>
                                                {b.skip ? "excluded" : `${Math.round((comp.weight ?? 0) * 100)}%`}
                                            </span>
                                        </div>
                                        {!b.skip && (
                                            <span style={{ fontSize: 16, fontWeight: 900, color: b.color, fontFamily: "var(--font-head)" }}>
                                                {(comp.points ?? 0).toFixed(1)} <span style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 500 }}>pts</span>
                                            </span>
                                        )}
                                    </div>

                                    {b.skip ? (
                                        <div style={{
                                            fontSize: 13, color: "var(--text-secondary)",
                                            padding: "8px 12px", borderRadius: 8,
                                            background: "var(--bg-surface-secondary)",
                                            border: "1px solid var(--border-inner)",
                                        }}>
                                            Not enough text to analyze reliably
                                        </div>
                                    ) : (
                                        <div style={{ height: 8, borderRadius: 99, background: "var(--border-inner)", overflow: "hidden" }}>
                                            <div style={{
                                                height: "100%", borderRadius: 99,
                                                width: `${clamp(comp.raw ?? 0)}%`,
                                                background: b.color,
                                                opacity: 0.85,
                                                transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)",
                                            }} />
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </Card>

                {/* NLP text summary (only when model ran) */}
                {!nlpInsuff && (
                    <Card>
                        <CardLabel>AI Security Insights</CardLabel>
                        {semanticExp ? (
                            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--text-primary)" }}>
                                {semanticExp}
                            </p>
                        ) : (
                            <p style={{ margin: 0, fontSize: 14, color: "var(--text-secondary)" }}>
                                No suspicious language patterns detected.
                            </p>
                        )}
                    </Card>
                )}
            </div>

            {/* Right — Red Flags & Trust Signals */}
            <Card>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                    {/* Red Flags */}
                    <div>
                        <CardLabel>
                            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <Flag size={12} color="#ef4444" /> Red Flags
                            </span>
                        </CardLabel>
                        {redFlags.length > 0 ? (
                            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                                {redFlags.map((f, i) => (
                                    <li key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 13.5, color: "var(--text-primary)", lineHeight: 1.5 }}>
                                        <Flag size={14} color="#ef4444" style={{ flexShrink: 0, marginTop: 2 }} />
                                        {f.label}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)" }}>No significant risk signals.</p>
                        )}
                    </div>

                    {/* Trust Signals */}
                    <div>
                        <CardLabel>
                            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <ShieldCheck size={12} color="#10b981" /> Trust Signals
                            </span>
                        </CardLabel>
                        {trustSigs.length > 0 ? (
                            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 10 }}>
                                {trustSigs.map((f, i) => (
                                    <li key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, fontSize: 13.5, color: "var(--text-primary)", lineHeight: 1.5 }}>
                                        <ShieldCheck size={14} color="#10b981" style={{ flexShrink: 0, marginTop: 2 }} />
                                        {f.label}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p style={{ margin: 0, fontSize: 13, color: "var(--text-secondary)" }}>No trust signals detected.</p>
                        )}
                    </div>
                </div>

                {/* Rule signals checklist */}
                {ruleSignals.length > 0 && (
                    <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid var(--border-inner)" }}>
                        <CardLabel>Heuristic Checks</CardLabel>
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                            {ruleSignals.map((sig, i) => (
                                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13.5 }}>
                                    <XCircle size={16} color="#ef4444" style={{ flexShrink: 0 }} aria-label="Failed check" />
                                    <span style={{ color: "var(--text-primary)" }}>{sig.message ?? sig.rule}</span>
                                </div>
                            ))}
                            {/* Implicit: any rule not in list = passed */}
                            <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13.5 }}>
                                <CheckCircle2 size={16} color="#10b981" style={{ flexShrink: 0 }} aria-label="Passed" />
                                <span style={{ color: "var(--text-secondary)" }}>All other safety checks passed</span>
                            </div>
                        </div>
                    </div>
                )}

                {ruleSignals.length === 0 && (
                    <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--border-inner)", display: "flex", alignItems: "center", gap: 10, fontSize: 13.5, color: "var(--risk-low)" }}>
                        <CheckCircle2 size={16} style={{ flexShrink: 0 }} /> All heuristic safety checks passed
                    </div>
                )}
            </Card>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 3: PDF Download
// ─────────────────────────────────────────────────────────────

function PdfDownload({ scanId }) {
    const [loading, setLoading] = useState(false);
    const [error,   setError]   = useState(null);

    async function handleDownload() {
        if (!scanId || loading) return;
        setLoading(true);
        setError(null);
        try {
            const resp = await fetch(`${API_BASE_URL}/scan/${scanId}/report.pdf`);
            if (!resp.ok) throw new Error(`Server returned ${resp.status}.`);
            const blob = await resp.blob();
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a");
            a.href     = url;
            a.download = `authentiscore_report_${scanId}.pdf`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            setError(err.message || "Download failed. Please try again.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <button
                id="btn-download-pdf"
                onClick={handleDownload}
                disabled={!scanId || loading}
                style={{
                    display: "inline-flex", alignItems: "center", gap: 10,
                    padding: "14px 32px", borderRadius: 12, fontSize: 15, fontWeight: 700,
                    cursor: scanId && !loading ? "pointer" : "not-allowed",
                    background: scanId && !loading
                        ? "linear-gradient(135deg, var(--accent-dark), var(--accent))"
                        : "var(--border-inner)",
                    color: scanId && !loading ? "var(--text-primary)" : "var(--text-muted)",
                    border: "none",
                    boxShadow: scanId && !loading ? "0 4px 20px rgba(0,112,243,0.25)" : "none",
                    transition: "all 0.2s",
                }}
                onMouseEnter={e => { if (scanId && !loading) e.currentTarget.style.boxShadow = "0 6px 28px rgba(0,112,243,0.4)"; }}
                onMouseLeave={e => { if (scanId && !loading) e.currentTarget.style.boxShadow = "0 4px 20px rgba(0,112,243,0.25)"; }}
            >
                {loading ? (
                    <>
                        <span style={{
                            width: 18, height: 18, borderRadius: "50%",
                            border: "2px solid var(--text-muted)",
                            borderTopColor: "var(--text-primary)",
                            animation: "spin 0.8s linear infinite",
                            display: "inline-block", flexShrink: 0,
                        }} />
                        Generating PDF…
                    </>
                ) : (
                    <><Download size={18} /> Download PDF Audit Report</>
                )}
            </button>
            {error && (
                <div style={{
                    display: "flex", alignItems: "center", gap: 8,
                    fontSize: 13, color: "var(--risk-high)",
                    padding: "8px 14px", borderRadius: 8,
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.2)",
                }}>
                    <AlertTriangle size={14} />
                    {error}
                    <button onClick={handleDownload} style={{
                        background: "none", border: "none", color: "var(--accent-light)",
                        cursor: "pointer", fontSize: 13, fontWeight: 700, padding: "0 4px",
                    }}>Retry</button>
                </div>
            )}
            {!scanId && (
                <p style={{ margin: 0, fontSize: 12, color: "var(--text-muted)" }}>
                    PDF available once scan is saved.
                </p>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Root export
// ─────────────────────────────────────────────────────────────

export default function ResultsPanel({ result }) {
    if (!result || result.final_score === undefined) return null;

    const scanId = result?.scan_id ?? null;

    return (
        <div style={{ marginTop: 36 }}>
            <ExecutiveSummary result={result} />
            <RiskBreakdown    result={result} />

            {/* Download */}
            <Card style={{ display: "flex", justifyContent: "center", padding: "28px" }}>
                <PdfDownload scanId={scanId} />
            </Card>
        </div>
    );
}
