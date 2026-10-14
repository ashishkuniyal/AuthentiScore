// ResultsPanel.jsx — Enterprise-grade results report (Scanner Upgrade B6 & B9)
// Layout: Top (Profile + Score Ring + Honest Confidence) → Middle (Why this score: 2 columns + Breakdown) → Bottom (Feedback + PDF + Deletion)
import { useState } from "react";
import {
    Flag, ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2,
    XCircle, Info, Users, UserCheck, FileText, ImageIcon, Lock,
    ExternalLink, Download, Bot, Zap, Target, Trash2, Check, ArrowLeft,
} from "lucide-react";
import RiskGauge from "./RiskGauge";
import { downloadReportPdf, submitScanFeedback, deleteScan } from "../services/api";

// ─────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────

function clamp(v) { return Math.min(Math.max(Number(v) || 0, 0), 100); }

function fmtNum(v) {
    if (v === null || v === undefined) return "N/A";
    return Number(v).toLocaleString();
}

/** Detect self-declared automation in the bio. */
function isDeclaredBot(bio = "") {
    const b = (bio || "").toLowerCase();
    return /\b(a bot for|official bot|automated account|this is a bot|bot account|automated by)\b/.test(b);
}

/** Normalize bio: convert literal \n escape sequences → real newlines. */
function normalizeBio(bio) {
    if (!bio) return "";
    return bio.replace(/\\n/g, "\n").replace(/\\r/g, "").trim();
}

/** Render bio text with clickable URLs. */
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
// Shared Card Wrapper
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

function CardLabel({ children, style = {} }) {
    return (
        <div style={{
            fontSize: 11, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase", color: "var(--text-secondary)",
            marginBottom: 16,
            ...style,
        }}>
            {children}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Stat Chip
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
// Section 1: Executive Summary (profile + score gauge + confidence)
// ─────────────────────────────────────────────────────────────

function ExecutiveSummary({ result, onBack, onNewScan }) {
    const profile     = result?.profile ?? {};
    const username    = profile.username ?? result?.username ?? "Unknown";
    const platform    = profile.platform ?? result?.platform ?? "Unknown";
    const url         = profile.profile_url ?? result?.profile_url ?? "";
    const bio         = normalizeBio(profile.bio ?? result?.collected_bio ?? "");
    const score       = clamp(result?.final_score ?? 0);
    const breakdown   = result?.score_breakdown ?? {};
    const sigUsed     = breakdown.signals_used ?? 3;
    const nlpInsuff   = breakdown.nlp_insufficient ?? false;
    const botDeclared = isDeclaredBot(bio) || result?.account_type === "automated_declared";
    const isAbstain   = Boolean(result?.abstain);

    // Provenance & trust level comes from backend collection.trust_level (Decision S8 / B4)
    const trustObj   = result?.collection?.trust_level || result?.trust_level;
    const trustLabel = trustObj?.label || (typeof trustObj === "string" ? trustObj : (result?.data_verified ? "Data verified" : null));
    const trustTooltip = trustObj?.tooltip || (result?.data_verified ? "Verified via direct collection" : "Public page unverified");
    const isVerified = trustObj?.code === "verified" || result?.data_verified === true;

    // Honest Confidence
    const confObj     = result?.confidence || {};
    const confScore   = confObj.score !== undefined ? Math.round(confObj.score * 100) : null;
    const confLevel   = confObj.level || (confScore !== null ? (confScore >= 75 ? "High" : confScore >= 50 ? "Medium" : "Low") : null);
    const confInterval = confObj.interval || null;
    const confReasons = confObj.reasons || [];
    const completeness = result?.data_completeness !== undefined ? Math.round(result.data_completeness * 100) : 100;
    const missingFeats = result?.missing_features || [];

    // Verdict sentence
    let verdict = "";
    if (result?.classification === "Insufficient Data") {
        verdict = "Insufficient profile data to reliably calculate an authenticity score.";
    } else if (isAbstain) {
        verdict = "Uncertain — manual review recommended. Score is borderline or feature completeness is restricted.";
    } else if (score < 34) {
        verdict = "This profile shows strong indicators of authentic organic activity.";
    } else if (score < 67) {
        verdict = "Moderate risk signals detected. Review behavioral factors below.";
    } else if (score < 90) {
        verdict = "Multiple high-risk indicators detected. High probability of inauthentic activity.";
    } else {
        verdict = "Critical synthetic or bot indicators detected. Very high risk of automation.";
    }
    if (botDeclared) {
        verdict = "Self-declared automated account. Score reflects behavioral posture rather than deceptive intent.";
    }

    const avatarGrads = [
        "linear-gradient(135deg,#4338ca,#8b5cf6)",
        "linear-gradient(135deg,#0ea5e9,#6366f1)",
        "linear-gradient(135deg,#059669,#0ea5e9)",
        "linear-gradient(135deg,#ea580c,#ef4444)",
    ];
    const avatarGrad = avatarGrads[(username.charCodeAt(0) || 0) % avatarGrads.length];

    return (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 20 }} className="results-grid-top">
            
            {/* Left Card — Profile Overview */}
            <Card>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <CardLabel style={{ marginBottom: 0 }}>Profile Overview</CardLabel>
                    {onBack && (
                        <button
                            id="btn-profile-back"
                            onClick={onBack}
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 6,
                                padding: "6px 14px",
                                borderRadius: 8,
                                background: "rgba(99, 102, 241, 0.12)",
                                border: "1px solid rgba(99, 102, 241, 0.25)",
                                color: "var(--accent-light)",
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: "pointer",
                                transition: "all 0.2s ease",
                            }}
                            onMouseEnter={e => {
                                e.currentTarget.style.background = "var(--accent)";
                                e.currentTarget.style.color = "#ffffff";
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.background = "rgba(99, 102, 241, 0.12)";
                                e.currentTarget.style.color = "var(--accent-light)";
                            }}
                        >
                            <ArrowLeft size={13} />
                            Back to Scan
                        </button>
                    )}
                </div>

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

                            {/* Trust level badge from backend collection.trust_level */}
                            {trustLabel && (
                                <span
                                    title={trustTooltip}
                                    style={{
                                        display: "inline-flex", alignItems: "center", gap: 5,
                                        padding: "2px 10px", borderRadius: 99, fontSize: 11, fontWeight: 700,
                                        background: isVerified ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                                        color: isVerified ? "var(--risk-low)" : "var(--risk-med)",
                                        border: `1px solid ${isVerified ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}`,
                                    }}
                                >
                                    <CheckCircle2 size={12} />
                                    {trustLabel}
                                </span>
                            )}

                            {/* Declared Bot Badge */}
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

                            {/* From 24h Cache Chip */}
                            {result?.from_cache && (
                                <span style={{
                                    display: "inline-flex", alignItems: "center", gap: 5,
                                    padding: "2px 10px", borderRadius: 99, fontSize: 11, fontWeight: 700,
                                    background: "rgba(14,165,233,0.12)", color: "#0ea5e9",
                                    border: "1px solid rgba(14,165,233,0.25)",
                                }}>
                                    <Zap size={12} />
                                    Served from 24h cache
                                </span>
                            )}

                            {result?.simulated && (
                                <span style={{
                                    display: "inline-flex", alignItems: "center", gap: 5,
                                    padding: "2px 10px", borderRadius: 99, fontSize: 11, fontWeight: 700,
                                    background: "rgba(245,158,11,0.12)", color: "var(--risk-med)",
                                    border: "1px solid rgba(245,158,11,0.25)",
                                }}>
                                    <AlertTriangle size={12} />
                                    Simulated demo data
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

                {/* Platform coverage warning if cross-platform model applicability is restricted */}
                {result?.model_applicable === false && (
                    <div style={{
                        marginBottom: 18, padding: "10px 14px", borderRadius: 10,
                        background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.25)",
                        fontSize: 12.5, color: "var(--risk-med)", display: "flex", alignItems: "center", gap: 8
                    }}>
                        <Info size={14} style={{ flexShrink: 0 }} />
                        <span>Platform Notice: Model v4 was trained primarily on Instagram profiles. Heuristic and rule weights are applied for {platform}, but ML calibration may be reduced.</span>
                    </div>
                )}

                {/* Stats grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 20 }}>
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

            {/* Right Card — Score Gauge & Honest Confidence */}
            <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16 }}>
                <CardLabel>Unified Authenticity Assessment</CardLabel>

                {/* Abstain Alert if score is uncertain */}
                {isAbstain && (
                    <div style={{
                        width: "100%", padding: "12px 16px", borderRadius: 10,
                        background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.3)",
                        display: "flex", alignItems: "center", gap: 10, color: "var(--risk-med)",
                        fontSize: 13, fontWeight: 600,
                    }}>
                        <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                        <span>Uncertain — manual review recommended (borderline confidence).</span>
                    </div>
                )}

                <RiskGauge score={score} animated />

                {/* Verdict text */}
                <p style={{
                    margin: 0, fontSize: 13.5, lineHeight: 1.6, textAlign: "center",
                    color: "var(--text-secondary)", maxWidth: 320,
                }}>
                    {verdict}
                </p>

                {/* Honest Confidence & Completeness Bar */}
                <div style={{
                    width: "100%", marginTop: 8, padding: "14px 16px", borderRadius: 12,
                    background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)",
                }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                            Honest Confidence
                        </span>
                        {confLevel && (
                            <span style={{
                                fontSize: 11, fontWeight: 800, padding: "2px 8px", borderRadius: 99,
                                background: confLevel === "High" ? "rgba(16,185,129,0.15)" : confLevel === "Medium" ? "rgba(99,102,241,0.15)" : "rgba(245,158,11,0.15)",
                                color: confLevel === "High" ? "var(--risk-low)" : confLevel === "Medium" ? "var(--accent-light)" : "var(--risk-med)",
                            }}>
                                {confScore !== null ? `${confScore}% (${confLevel})` : confLevel}
                            </span>
                        )}
                    </div>

                    {/* Completeness Bar */}
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-muted)", marginBottom: 4 }}>
                        <span>Data Completeness: {completeness}%</span>
                        {confInterval && <span>CI: [{confInterval[0]?.toFixed(2)}, {confInterval[1]?.toFixed(2)}]</span>}
                    </div>
                    <div style={{ height: 6, borderRadius: 99, background: "var(--border-inner)", overflow: "hidden", marginBottom: 8 }}>
                        <div style={{ height: "100%", width: `${completeness}%`, background: completeness >= 80 ? "var(--risk-low)" : "var(--risk-med)", borderRadius: 99 }} />
                    </div>

                    {missingFeats.length > 0 && (
                        <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginBottom: 6 }}>
                            Unobserved: {missingFeats.join(", ")}
                        </div>
                    )}

                    {confReasons.length > 0 && (
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.4 }}>
                            {confReasons[0]}
                        </div>
                    )}
                </div>

                {/* Signals Used Chip */}
                {nlpInsuff && (
                    <div style={{
                        display: "inline-flex", alignItems: "center", gap: 6,
                        padding: "5px 12px", borderRadius: 99, fontSize: 12, fontWeight: 600,
                        background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)",
                        color: "var(--text-secondary)",
                    }}>
                        <Info size={13} />
                        Based on {sigUsed} of 3 signals (bio skipped)
                    </div>
                )}
            </Card>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 2: Why this score — Two-Column Unified Reasons (A8 & B6)
// ─────────────────────────────────────────────────────────────

function WhyThisScore({ reasons = [], ruleSignals = [], topMlFactors = [] }) {
    // Partition reasons into factors raising risk vs factors lowering risk
    const raising = reasons.filter(r => r.direction === "raises_risk" || r.impact > 0);
    const lowering = reasons.filter(r => r.direction === "lowers_risk" || r.impact < 0);

    // Fallbacks if unified reasons not available
    const displayRaising = raising.length > 0
        ? raising
        : [
            ...ruleSignals.map(s => ({ source: "rule", impact: s.weight || 10, human_label: s.message || s.rule })),
            ...topMlFactors.filter(f => f.is_risk).map(f => ({ source: "ml", impact: 15, human_label: f.label })),
        ];

    const displayLowering = lowering.length > 0
        ? lowering
        : topMlFactors.filter(f => !f.is_risk).map(f => ({ source: "trust", impact: -15, human_label: f.label }));

    const getSourceBadge = (source) => {
        const s = (source || "").toLowerCase();
        if (s === "ml") return { label: "ML", bg: "rgba(99,102,241,0.12)", color: "var(--accent-light)" };
        if (s === "nlp") return { label: "NLP", bg: "rgba(167,139,250,0.12)", color: "#a78bfa" };
        if (s === "rule") return { label: "RULE", bg: "rgba(249,115,22,0.12)", color: "#f97316" };
        if (s === "trust") return { label: "TRUST", bg: "rgba(16,185,129,0.12)", color: "var(--risk-low)" };
        return { label: "SIGNAL", bg: "rgba(148,163,184,0.12)", color: "var(--text-secondary)" };
    };

    return (
        <Card style={{ marginBottom: 20 }}>
            <CardLabel>Why This Score — Explainability Matrix</CardLabel>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 24 }}>
                
                {/* Column 1: Factors Raising Risk */}
                <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                        <Flag size={14} color="#ef4444" />
                        <span style={{ fontSize: 13, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--risk-high)" }}>
                            Factors Raising Risk ({displayRaising.length})
                        </span>
                    </div>

                    {displayRaising.length > 0 ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                            {displayRaising.map((item, idx) => {
                                const badge = getSourceBadge(item.source);
                                return (
                                    <div
                                        key={idx}
                                        style={{
                                            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
                                            padding: "10px 14px", borderRadius: 10,
                                            background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.15)",
                                        }}
                                    >
                                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                            <span style={{
                                                fontSize: 10, fontWeight: 800, padding: "2px 6px", borderRadius: 6,
                                                background: badge.bg, color: badge.color,
                                            }}>
                                                {badge.label}
                                            </span>
                                            <span style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 500 }}>
                                                {item.human_label || item.description}
                                            </span>
                                        </div>
                                        {item.impact !== undefined && (
                                            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--risk-high)", whiteSpace: "nowrap" }}>
                                                +{Math.abs(item.impact).toFixed(0)} pts
                                            </span>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "12px", background: "var(--bg-surface-secondary)", borderRadius: 10 }}>
                            No significant high-risk behavioral patterns detected.
                        </div>
                    )}
                </div>

                {/* Column 2: Factors Lowering Risk */}
                <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                        <ShieldCheck size={14} color="#10b981" />
                        <span style={{ fontSize: 13, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--risk-low)" }}>
                            Factors Lowering Risk ({displayLowering.length})
                        </span>
                    </div>

                    {displayLowering.length > 0 ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                            {displayLowering.map((item, idx) => {
                                const badge = getSourceBadge(item.source || "trust");
                                return (
                                    <div
                                        key={idx}
                                        style={{
                                            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
                                            padding: "10px 14px", borderRadius: 10,
                                            background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.15)",
                                        }}
                                    >
                                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                            <span style={{
                                                fontSize: 10, fontWeight: 800, padding: "2px 6px", borderRadius: 6,
                                                background: badge.bg, color: badge.color,
                                            }}>
                                                {badge.label}
                                            </span>
                                            <span style={{ fontSize: 13, color: "var(--text-primary)", fontWeight: 500 }}>
                                                {item.human_label || item.description}
                                            </span>
                                        </div>
                                        {item.impact !== undefined && (
                                            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--risk-low)", whiteSpace: "nowrap" }}>
                                                -{Math.abs(item.impact).toFixed(0)} pts
                                            </span>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: "12px", background: "var(--bg-surface-secondary)", borderRadius: 10 }}>
                            No established trust patterns detected.
                        </div>
                    )}
                </div>

            </div>
        </Card>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 3: Risk Breakdown Components
// ─────────────────────────────────────────────────────────────

function RiskBreakdown({ result }) {
    const breakdown    = result?.score_breakdown ?? {};
    const components   = breakdown.components ?? {};
    const nlpInsuff    = breakdown.nlp_insufficient ?? false;
    const nlpSignals   = result?.nlp_signals ?? {};
    const semanticExp  = nlpSignals.semantic_explanation ?? "";

    const bars = [
        { key: "ml", label: "Ensemble Machine Learning", icon: Zap, color: "#818cf8" },
        { key: "nlp", label: "Semantic Bio & Text Analysis", icon: Target, color: "#a78bfa", skip: nlpInsuff },
        { key: "rules", label: "Heuristic Rules & Safety Checks", icon: ShieldAlert, color: "#f97316" },
    ];

    return (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20, marginBottom: 20 }}>
            <Card>
                <CardLabel>Engine Contribution Breakdown</CardLabel>
                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
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
                                            {b.skip ? "excluded" : `${Math.round((comp.weight ?? 0) * 100)}% weight`}
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
                                        Not enough bio text to analyze reliably. NLP component bypassed to prevent distortion.
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

            {!nlpInsuff && semanticExp && (
                <Card>
                    <CardLabel>Semantic Insights</CardLabel>
                    <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: "var(--text-primary)" }}>
                        {semanticExp}
                    </p>
                </Card>
            )}
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 4: Feedback Verdicts (A9 & B6)
// ─────────────────────────────────────────────────────────────

function FeedbackSection({ scanId }) {
    const [status, setStatus] = useState(null);
    const [submitting, setSubmitting] = useState(false);

    async function handleFeedback(verdict) {
        if (!scanId || submitting) return;
        setSubmitting(true);
        try {
            await submitScanFeedback(scanId, { user_verdict: verdict });
            setStatus(verdict);
        } catch (e) {
            console.error("Feedback error:", e);
        } finally {
            setSubmitting(false);
        }
    }

    if (status) {
        return (
            <div style={{ textAlign: "center", padding: "16px", color: "var(--risk-low)", fontSize: 13.5, fontWeight: 600 }}>
                ✓ Thank you! Verdict recorded as <strong style={{ textTransform: "capitalize" }}>{status}</strong>. This feedback is logged for model calibration.
            </div>
        );
    }

    return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)" }}>
                Was this verdict accurate?
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
                <button
                    onClick={() => handleFeedback("authentic")}
                    disabled={submitting || !scanId}
                    className="btn-ghost"
                    style={{ fontSize: 13, padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(16,185,129,0.3)", color: "var(--risk-low)" }}
                >
                    <Check size={14} style={{ display: "inline", marginRight: 4 }} />
                    Authentic
                </button>
                <button
                    onClick={() => handleFeedback("inauthentic")}
                    disabled={submitting || !scanId}
                    className="btn-ghost"
                    style={{ fontSize: 13, padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(239,68,68,0.3)", color: "var(--risk-high)" }}
                >
                    <XCircle size={14} style={{ display: "inline", marginRight: 4 }} />
                    Inauthentic
                </button>
                <button
                    onClick={() => handleFeedback("bot")}
                    disabled={submitting || !scanId}
                    className="btn-ghost"
                    style={{ fontSize: 13, padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(99,102,241,0.3)", color: "var(--accent-light)" }}
                >
                    <Bot size={14} style={{ display: "inline", marginRight: 4 }} />
                    Declared Bot
                </button>
            </div>
        </div>
    );
}

// ─────────────────────────────────────────────────────────────
// Section 5: PDF Export & Compliance Deletion (B8)
// ─────────────────────────────────────────────────────────────

function ActionsSection({ scanId, onDeleteScan, onBack }) {
    const [downloading, setDownloading] = useState(false);
    const [error,       setError]       = useState(null);
    const [deleting,    setDeleting]    = useState(false);
    const [confirmDel,  setConfirmDel]  = useState(false);

    async function handleDownload() {
        if (!scanId || downloading) return;
        setDownloading(true);
        setError(null);
        try {
            const blob = await downloadReportPdf(scanId);
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a");
            a.href     = url;
            a.download = `authentiscore_report_${scanId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (err) {
            setError(err.message || "Download failed. Please try again.");
        } finally {
            setDownloading(false);
        }
    }

    async function handleDelete() {
        if (!scanId || deleting) return;
        setDeleting(true);
        try {
            await deleteScan(scanId);
            onDeleteScan?.();
        } catch (err) {
            setError(err.message || "Failed to delete scan record.");
            setDeleting(false);
            setConfirmDel(false);
        }
    }

    return (
        <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "28px" }}>
            <FeedbackSection scanId={scanId} />

            <div style={{ width: "100%", height: 1, background: "var(--border-inner)", margin: "8px 0" }} />

            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
                {/* Back to Scan Button */}
                {onBack && (
                    <button
                        id="btn-actions-back"
                        onClick={onBack}
                        className="btn-ghost"
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "12px 24px",
                            fontSize: 14,
                            fontWeight: 600,
                            borderRadius: 12,
                            border: "1px solid var(--border-hover)",
                        }}
                    >
                        <ArrowLeft size={16} />
                        Back to Scan
                    </button>
                )}

                {/* PDF Download Button */}
                <button
                    id="btn-download-pdf"
                    onClick={handleDownload}
                    disabled={!scanId || downloading}
                    style={{
                        display: "inline-flex", alignItems: "center", gap: 10,
                        padding: "12px 28px", borderRadius: 12, fontSize: 14, fontWeight: 700,
                        cursor: scanId && !downloading ? "pointer" : "not-allowed",
                        background: scanId && !downloading
                            ? "linear-gradient(135deg, var(--accent-dark), var(--accent))"
                            : "var(--border-inner)",
                        color: scanId && !downloading ? "var(--text-primary)" : "var(--text-muted)",
                        border: "none",
                        boxShadow: scanId && !downloading ? "0 4px 20px rgba(99,102,241,0.25)" : "none",
                    }}
                >
                    {downloading ? (
                        <>
                            <span style={{
                                width: 16, height: 16, borderRadius: "50%",
                                border: "2px solid var(--text-muted)", borderTopColor: "var(--text-primary)",
                                animation: "spin 0.8s linear infinite", display: "inline-block",
                            }} />
                            Generating Audit PDF…
                        </>
                    ) : (
                        <><Download size={16} /> Download Audit Report</>
                    )}
                </button>

                {/* Compliance Deletion (B8) */}
                {scanId && !confirmDel && (
                    <button
                        onClick={() => setConfirmDel(true)}
                        className="btn-ghost"
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--text-muted)" }}
                    >
                        <Trash2 size={14} /> Delete Scan
                    </button>
                )}

                {scanId && confirmDel && (
                    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                        <span style={{ color: "var(--risk-high)" }}>Permanently delete?</span>
                        <button
                            onClick={handleDelete}
                            disabled={deleting}
                            style={{ background: "#ef4444", color: "#fff", border: "none", borderRadius: 6, padding: "4px 12px", fontSize: 12, cursor: "pointer", fontWeight: 700 }}
                        >
                            {deleting ? "Deleting…" : "Confirm"}
                        </button>
                        <button
                            onClick={() => setConfirmDel(false)}
                            className="btn-ghost"
                            style={{ fontSize: 12, padding: "4px 8px" }}
                        >
                            Cancel
                        </button>
                    </div>
                )}
            </div>

            {error && (
                <div style={{
                    display: "flex", alignItems: "center", gap: 8, fontSize: 13,
                    color: "var(--risk-high)", padding: "8px 14px", borderRadius: 8,
                    background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
                }}>
                    <AlertTriangle size={14} />
                    {error}
                </div>
            )}
        </Card>
    );
}

// ─────────────────────────────────────────────────────────────
// Root Export
// ─────────────────────────────────────────────────────────────

export default function ResultsPanel({ result, onDeleteScan, onBack, onNewScan }) {
    if (!result || result.classification === undefined) return null;

    const scanId = result?.scan_id ?? null;
    const isInsufficient = result.classification === "Insufficient Data";

    return (
        <div style={{ marginTop: 36 }}>
            <ExecutiveSummary result={result} onBack={onBack} onNewScan={onNewScan} />

            {!isInsufficient && (
                <>
                    <WhyThisScore
                        reasons={result.reasons || []}
                        ruleSignals={result.rule_signals || []}
                        topMlFactors={result.top_ml_factors || []}
                    />
                    <RiskBreakdown result={result} />
                </>
            )}

            <ActionsSection scanId={scanId} onDeleteScan={onDeleteScan} onBack={onBack} />
        </div>
    );
}
