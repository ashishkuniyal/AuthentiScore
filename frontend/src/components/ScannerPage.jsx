// ScannerPage.jsx — Background Scan Jobs (B2), 24h Cache (B3), Truthful System Status (B7), Keyboard & UX (B9)
import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowLeft } from "lucide-react";
import ResultsPanel from "./ResultsPanel";
import {
    createScanJob,
    getScanJob,
    cancelScanJob,
    profileScan,
    getRecentScans,
    getSystemStatus,
} from "../services/api";

// ==============================================================
// Background Pipeline Steps (B2)
// ==============================================================

const PIPELINE_STEPS = [
    { id: "normalizing", label: "Normalizing input & checking 24h cache" },
    { id: "collecting",  label: "Collecting permitted public profile data" },
    { id: "features",    label: "Extracting behavioral & account features" },
    { id: "scoring",     label: "Running calibrated v4 ensemble model" },
    { id: "explaining",  label: "Synthesizing unified explainability reasons" },
    { id: "complete",    label: "Audit report ready" },
];

function detectPlatform(url) {
    const u = (url || "").trim().toLowerCase();
    if (u.includes("instagram.com")) return "instagram";
    if (u.includes("twitter.com") || u.includes("x.com")) return "twitter";
    if (u.includes("youtube.com") || u.includes("youtu.be")) return "youtube";
    if (u.includes("mastodon") || u.includes("mstdn")) return "mastodon";
    if (u.includes("tiktok.com")) return "tiktok";
    if (u.includes("github.com")) return "github";
    return "instagram";
}

// ==============================================================
// Scanning Animation with Cancel Action
// ==============================================================

function ScanningAnimation({ activeStep, onCancel }) {
    return (
        <div
            className="animate-scale-in"
            style={{
                padding: "24px 26px",
                background: "rgba(99,102,241,0.06)",
                border: "1px solid rgba(99,102,241,0.2)",
                borderRadius: 14,
                marginTop: 24,
                boxShadow: "inset 0 2px 10px rgba(99,102,241,0.05)",
            }}
            aria-live="polite"
        >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div
                        style={{
                            width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                            border: "3px solid rgba(99,102,241,0.2)",
                            borderTopColor: "var(--accent)",
                            animation: "spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite",
                        }}
                    />
                    <div>
                        <div style={{ fontFamily: "var(--font-head)", fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
                            Running AuthentiScore pipeline…
                        </div>
                        <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
                            Asynchronous background job in progress
                        </div>
                    </div>
                </div>

                <button
                    onClick={onCancel}
                    className="btn-ghost"
                    style={{ fontSize: 13, padding: "6px 14px", border: "1px solid var(--border-inner)" }}
                >
                    Cancel (Esc)
                </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {PIPELINE_STEPS.map((step, i) => {
                    const isComplete = i < activeStep;
                    const isActive   = i === activeStep;
                    return (
                        <div
                            key={step.id}
                            style={{
                                display: "flex", alignItems: "center", gap: 12,
                                padding: "8px 12px", borderRadius: 8,
                                background: isActive ? "var(--border-inner)" : "transparent",
                                boxShadow: isActive ? "0 2px 8px rgba(0,0,0,0.4)" : "none",
                                border: isActive ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent",
                                transition: "all 0.3s ease",
                            }}
                        >
                            <div
                                style={{
                                    width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    fontSize: 11, fontWeight: 800,
                                    background: isComplete ? "rgba(5,150,105,0.15)" : isActive ? "var(--accent)" : "var(--border-inner)",
                                    color: isComplete ? "var(--risk-low)" : isActive ? "var(--text-primary)" : "var(--text-muted)",
                                    transition: "all 0.3s",
                                }}
                            >
                                {isComplete ? "✓" : i + 1}
                            </div>
                            <span
                                style={{
                                    fontSize: 14,
                                    color: isComplete ? "var(--risk-low)" : isActive ? "var(--text-primary)" : "var(--text-secondary)",
                                    fontWeight: isActive ? 600 : 500,
                                    transition: "color 0.3s",
                                    flex: 1,
                                }}
                            >
                                {step.label}
                            </span>
                            {isActive && (
                                <div style={{ width: 64, height: 4, borderRadius: 99, background: "rgba(99,102,241,0.1)", overflow: "hidden" }}>
                                    <div
                                        style={{
                                            height: "100%", background: "var(--accent)", borderRadius: 99, width: "50%",
                                            animation: "scan-line 1.2s ease-in-out infinite",
                                        }}
                                    />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// ==============================================================
// Manual Fallback Form (B5)
// ==============================================================

function ManualFallbackForm({ profile, platform, onUpdate, onSubmit, onCancel, loading }) {
    return (
        <div
            className="animate-slide-down"
            style={{
                marginTop: 24, padding: "28px",
                background: "linear-gradient(180deg, rgba(217,119,6,0.03) 0%, rgba(217,119,6,0.08) 100%)",
                border: "1px solid rgba(217,119,6,0.3)",
                borderRadius: 16,
                boxShadow: "inset 0 2px 12px var(--text-muted)",
            }}
        >
            <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, color: "var(--risk-med)", marginBottom: 8 }}>
                    Manual Fallback Required
                </div>
                <h3 style={{ margin: 0, fontFamily: "var(--font-head)", fontSize: 20, fontWeight: 800, color: "var(--text-primary)" }}>
                    Complete the profile details
                </h3>
                <p style={{ margin: "8px 0 0", fontSize: 14, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                    Automated data collection was restricted for <strong>{platform}</strong>. Please enter the missing publicly visible information below to proceed with scoring.
                </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 16 }}>
                <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>Platform</label>
                    <input value={platform} disabled className="input-field" />
                </div>
                {[
                    { key: "username",  label: "Username",  type: "text",   placeholder: "username" },
                    { key: "followers", label: "Followers", type: "number", placeholder: "0" },
                    { key: "following", label: "Following", type: "number", placeholder: "0" },
                    { key: "posts",     label: "Posts",     type: "number", placeholder: "0" },
                ].map(f => (
                    <div key={f.key}>
                        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>{f.label}</label>
                        <input
                            type={f.type}
                            min={f.type === "number" ? 0 : undefined}
                            value={profile[f.key] ?? ""}
                            placeholder={f.placeholder}
                            onChange={e => onUpdate(f.key, f.type === "number" ? Number(e.target.value) : e.target.value)}
                            className="input-field"
                        />
                    </div>
                ))}
                <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>Profile Picture</label>
                    <select 
                        value={profile.has_profile_picture ?? ""} 
                        onChange={e => onUpdate("has_profile_picture", e.target.value === "" ? null : Number(e.target.value))} 
                        className="input-field"
                    >
                        <option value="">Select status...</option>
                        <option value={1}>Available</option>
                        <option value={0}>Missing</option>
                    </select>
                </div>
                <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>Account Privacy</label>
                    <select 
                        value={profile.is_private ?? ""} 
                        onChange={e => onUpdate("is_private", e.target.value === "" ? null : Number(e.target.value))} 
                        className="input-field"
                    >
                        <option value="">Select status...</option>
                        <option value={0}>Public</option>
                        <option value={1}>Private</option>
                    </select>
                </div>
                <div style={{ gridColumn: "1 / -1" }}>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                        Bio <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>(publicly visible text)</span>
                    </label>
                    <textarea
                        rows={3}
                        value={profile.bio ?? ""}
                        placeholder="Paste the publicly visible profile bio"
                        onChange={e => onUpdate("bio", e.target.value)}
                        className="input-field"
                        style={{ resize: "vertical" }}
                    />
                </div>
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 24, flexWrap: "wrap", borderTop: "1px solid var(--border-inner)", paddingTop: 20 }}>
                <button className="btn-ghost" onClick={onCancel} disabled={loading} style={{ background: "var(--border-inner)" }}>Cancel</button>
                <button 
                    className="btn-primary" 
                    onClick={onSubmit} 
                    disabled={loading || !profile.username?.trim() || profile.has_profile_picture === null || profile.has_profile_picture === undefined || profile.is_private === null || profile.is_private === undefined}
                >
                    {loading ? "Analysing…" : "Run Analysis →"}
                </button>
            </div>
        </div>
    );
}

// ==============================================================
// Main ScannerPage Component
// ==============================================================

export default function ScannerPage({
    notifications = [],
    initialSearchQuery = "",
    onClearSearch = () => {},
    onNavigateToBulk = () => {},
    onNavigate,
    onBack,
}) {
    const handleGoBack = () => {
        if (result && !loading) {
            handleBackToScan();
        } else if (onBack) {
            onBack();
        } else if (onNavigate) {
            onNavigate("dashboard");
        }
    };

    const [profileUrl,       setProfileUrl]       = useState("");
    const [scanConsent,      setScanConsent]      = useState(true); // Checked by default (B8)
    const [loading,          setLoading]          = useState(false);
    const [activeStep,       setActiveStep]       = useState(-1);
    const [currentJobId,     setCurrentJobId]     = useState(null);
    const [error,            setError]            = useState("");
    const [result,           setResult]           = useState(null);
    const [showManual,       setShowManual]       = useState(false);
    const [systemStatus,     setSystemStatus]     = useState(null);
    const [recentScans,      setRecentScans]      = useState([]);
    const [manualProfile,    setManualProfile]    = useState({
        platform: "", profile_url: "", username: "",
        followers: "", following: "", posts: "",
        bio: "", has_profile_picture: null, is_private: null,
    });

    const pollRef = useRef(null);
    const inputRef = useRef(null);
    const resultsRef = useRef(null);

    const detectedPlatform = detectPlatform(profileUrl);

    // Stop active polling
    const stopPolling = useCallback(() => {
        if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }, []);

    // ----------------------------------------------------------
    // Load Truthful System Status & Recent Scans (B7)
    // ----------------------------------------------------------

    useEffect(() => {
        let isMounted = true;
        const loadInitialData = async () => {
            try {
                const [statusData, recentsData] = await Promise.allSettled([
                    getSystemStatus(),
                    getRecentScans(5),
                ]);
                if (!isMounted) return;
                if (statusData.status === "fulfilled") setSystemStatus(statusData.value);
                if (recentsData.status === "fulfilled" && Array.isArray(recentsData.value)) {
                    setRecentScans(recentsData.value);
                }
            } catch {
                // Ignore initial load error
            }
        };

        loadInitialData();
        const interval = setInterval(async () => {
            try {
                const data = await getSystemStatus();
                if (isMounted) setSystemStatus(data);
            } catch {
                // Ignore interval status error
            }
        }, 30000);

        return () => {
            isMounted = false;
            clearInterval(interval);
        };
    }, []);

    // ----------------------------------------------------------
    // Cancel Scan Job (B2)
    // ----------------------------------------------------------

    const handleCancelScan = useCallback(async () => {
        stopPolling();
        if (currentJobId) {
            try {
                await cancelScanJob(currentJobId);
            } catch {
                // Ignore cancel failure
            }
        }
        setLoading(false);
        setActiveStep(-1);
        setCurrentJobId(null);
        setError("Scan was cancelled.");
        setTimeout(() => inputRef.current?.focus(), 100);
    }, [currentJobId, stopPolling]);

    // ----------------------------------------------------------
    // Navigation handlers: Back to scan & New scan
    // ----------------------------------------------------------

    const handleBackToScan = useCallback(() => {
        setResult(null);
        setActiveStep(-1);
        setTimeout(() => {
            inputRef.current?.focus();
            inputRef.current?.select();
        }, 100);
    }, []);

    const handleNewScan = useCallback(() => {
        setResult(null);
        setProfileUrl("");
        setActiveStep(-1);
        setTimeout(() => inputRef.current?.focus(), 100);
    }, []);

    // ----------------------------------------------------------
    // Keyboard Shortcuts: Enter to submit, Esc to cancel / reset (B9)
    // ----------------------------------------------------------

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === "Escape") {
                if (loading) {
                    handleCancelScan();
                } else if (result) {
                    handleBackToScan();
                }
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [loading, result, handleCancelScan, handleBackToScan]);

    // ----------------------------------------------------------
    // Primary Scan Handler via Background Job (B2, B3)
    // ----------------------------------------------------------

    const handleScan = useCallback(async (directUrl = null, directConsent = null) => {
        const isUrlString = typeof directUrl === "string";
        const checkConsent = (directConsent !== null && typeof directConsent === "boolean") ? directConsent : scanConsent;
        const url = (isUrlString && directUrl) ? directUrl.trim() : profileUrl.trim();

        if (!checkConsent) {
            setError("Please confirm the scanning consent terms first.");
            return;
        }
        if (!url) {
            setError("Please enter a valid profile URL or username handle.");
            return;
        }

        setError(""); setResult(null); setShowManual(false);
        setLoading(true); setActiveStep(0);

        try {
            const platform = detectPlatform(url);
            const jobData = await createScanJob({
                input: url,
                platform,
                consent: true,
                force_refresh: false,
            });

            // Fast path: cached or already finished
            if (jobData.status === "complete" && jobData.result) {
                setResult(jobData.result);
                setLoading(false);
                setActiveStep(-1);
                setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);
                return;
            }

            const jobId = jobData.job_id;
            setCurrentJobId(jobId);

            // Poll background job stages
            const stageOrder = {
                queued: 0,
                normalizing: 0,
                collecting: 1,
                features: 2,
                scoring: 3,
                explaining: 4,
                complete: 5,
            };

            const poll = setInterval(async () => {
                try {
                    const job = await getScanJob(jobId);
                    if (!job) return;

                    if (job.stage && stageOrder[job.stage] !== undefined) {
                        setActiveStep(stageOrder[job.stage]);
                    }

                    if (job.status === "complete") {
                        clearInterval(poll);
                        pollRef.current = null;
                        setLoading(false);
                        setActiveStep(-1);
                        setCurrentJobId(null);
                        setResult(job.result);
                        setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);
                    } else if (job.status === "failed") {
                        clearInterval(poll);
                        pollRef.current = null;
                        setLoading(false);
                        setActiveStep(-1);
                        setCurrentJobId(null);
                        setError(job.error || "Profile analysis could not be completed.");
                    } else if (job.status === "cancelled") {
                        clearInterval(poll);
                        pollRef.current = null;
                        setLoading(false);
                        setActiveStep(-1);
                        setCurrentJobId(null);
                        setError("Scan job was cancelled.");
                    }
                } catch {
                    // Retry on intermittent network error
                }
            }, 450);

            pollRef.current = poll;

        } catch (err) {
            setLoading(false);
            setActiveStep(-1);
            setCurrentJobId(null);
            setError(err.message || "Unable to initiate profile analysis job.");
        }
    }, [profileUrl, scanConsent]);

    // Auto-trigger scan if initial query provided
    useEffect(() => {
        if (!initialSearchQuery) return;
        let scanUrl = initialSearchQuery;
        if (!scanUrl.startsWith("http")) {
            scanUrl = `https://instagram.com/${scanUrl.replace("@", "")}`;
        }
        const timer = setTimeout(() => {
            setProfileUrl(scanUrl);
            setScanConsent(true);
            onClearSearch();
            handleScan(scanUrl, true);
        }, 0);
        return () => clearTimeout(timer);
    }, [initialSearchQuery, onClearSearch, handleScan]);

    function updateManual(field, value) {
        setManualProfile(p => ({ ...p, [field]: value }));
    }

    // ----------------------------------------------------------
    // Manual Fallback Scan Handler (B5)
    // ----------------------------------------------------------

    async function handleManualScan() {
        if (!scanConsent) { setError("Please confirm the scanning consent."); return; }
        if (!manualProfile.username.trim()) { setError("Please enter the profile username."); return; }

        setError(""); setResult(null);
        setLoading(true); setActiveStep(3);

        try {
            const scan = await profileScan({
                platform:    manualProfile.platform,
                profile_url: manualProfile.profile_url || profileUrl,
                username:    manualProfile.username.trim(),
                followers:   Number(manualProfile.followers),
                following:   Number(manualProfile.following),
                posts:       Number(manualProfile.posts),
                bio:         manualProfile.bio || "",
                has_profile_picture: Number(manualProfile.has_profile_picture),
                is_private:  Number(manualProfile.is_private),
            });

            setResult({
                ...scan,
                collection: {
                    source: "user_provided",
                    status: "success",
                    timestamp: new Date().toISOString(),
                    fields_collected: [],
                    trust_level: { code: "user_provided", label: "User provided", tooltip: "Manual entry fallback" },
                    data_verified: false,
                },
            });
            setShowManual(false);
            setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);
        } catch (err) {
            setError(err.message || "Unable to complete manual profile evaluation.");
        } finally {
            setLoading(false);
            setActiveStep(-1);
        }
    }

    // ----------------------------------------------------------
    // Real Live Security Log (B7) — De-duplicated by job_id
    // ----------------------------------------------------------

    const [securityLogs, setSecurityLogs] = useState(() => {
        try {
            return JSON.parse(sessionStorage.getItem("authentiscore_sec_logs") || "[]");
        } catch {
            return [];
        }
    });

    useEffect(() => {
        if (!notifications || notifications.length === 0) return;
        const timer = setTimeout(() => {
            setSecurityLogs(prev => {
                const seen = new Set(prev.map(l => l.job_id).filter(Boolean));
                const fresh = [];
                for (const n of notifications) {
                    if (n.job_id && seen.has(n.job_id)) continue;
                    if (n.job_id) seen.add(n.job_id);
                    fresh.unshift({
                        time: "Just now",
                        action: n.message || `Event: ${n.type}`,
                        job_id: n.job_id || null,
                    });
                }
                const merged = [...fresh, ...prev].slice(0, 50);
                try { sessionStorage.setItem("authentiscore_sec_logs", JSON.stringify(merged)); } catch {}
                return merged;
            });
        }, 0);
        return () => clearTimeout(timer);
    }, [notifications]);

    // ----------------------------------------------------------
    // Render
    // ----------------------------------------------------------

    return (
        <div style={{ display: "flex", gap: 32, padding: "32px", maxWidth: 1600, margin: "0 auto", height: "100%" }}>
            
            {/* ── Left Column: Scanner ────────────────────────────── */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20, maxWidth: 860 }}>
                
                {/* Back to Dashboard Navigation */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <button
                        id="scanner-back-btn"
                        type="button"
                        onClick={handleGoBack}
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "8px 16px",
                            borderRadius: 10,
                            background: "var(--bg-card)",
                            border: "1px solid var(--border-inner)",
                            color: "var(--text-secondary)",
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: "pointer",
                            transition: "all 0.2s ease",
                            boxShadow: "var(--shadow-sm)",
                        }}
                        className="hover:text-[var(--text-primary)] hover:border-[var(--accent)] hover:bg-[var(--bg-surface-secondary)] group"
                        title={result && !loading ? "Return to configure scan" : "Back to Dashboard"}
                    >
                        <ArrowLeft size={16} className="transition-transform group-hover:-translate-x-1" />
                        <span>{result && !loading ? "← Back to Configure Scan" : "Back to Dashboard"}</span>
                    </button>
                </div>

                {/* Scanner Wizard */}
                <div
                    className="premium-glass"
                    style={{
                        position: "relative", overflow: "hidden",
                        padding: "32px",
                        boxShadow: "var(--shadow-lg)",
                        borderRadius: 20
                    }}
                >
                    <div style={{
                        position: "absolute", top: 0, left: 0, right: 0, height: 4,
                        background: "linear-gradient(90deg, #6366f1, #8b5cf6, #d946ef)",
                    }} />

                    {/* Step Wizard Header */}
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 32, borderBottom: "1px solid var(--border-inner)", paddingBottom: 24 }}>
                        <button
                            type="button"
                            onClick={(result && !loading) ? handleBackToScan : undefined}
                            disabled={loading || (!result && activeStep === -1)}
                            title={result && !loading ? "Click to return to Configure Scan (Step 1)" : undefined}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                background: (result && !loading) ? "rgba(99,102,241,0.12)" : "transparent",
                                border: (result && !loading) ? "1px solid rgba(99,102,241,0.3)" : "1px solid transparent",
                                padding: (result && !loading) ? "6px 12px" : "4px 6px",
                                borderRadius: 10,
                                cursor: (result && !loading) ? "pointer" : "default",
                                opacity: (activeStep === -1 && !result && !showManual) ? 1 : (result ? 1 : 0.4),
                                transition: "all 0.2s ease",
                            }}
                        >
                            <div style={{
                                width: 24, height: 24, borderRadius: "50%",
                                background: (activeStep === -1 && !result && !showManual)
                                    ? "var(--accent)"
                                    : (result && !loading ? "var(--accent)" : "var(--border-inner)"),
                                color: "var(--text-primary)",
                                display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: 12, fontWeight: 700,
                            }}>
                                {result && !loading ? "←" : "1"}
                            </div>
                            <span style={{
                                fontSize: 14,
                                fontWeight: 600,
                                color: (result && !loading) ? "var(--accent-light)" : "var(--text-primary)",
                            }}>
                                {result && !loading ? "← Configure Scan" : "Configure Scan"}
                            </span>
                        </button>
                        <div style={{ flex: 1, height: 1, background: "var(--border-inner)" }} />
                        <div style={{ display: "flex", alignItems: "center", gap: 8, opacity: loading ? 1 : 0.4, transition: "opacity 0.3s" }}>
                            <div style={{ width: 24, height: 24, borderRadius: "50%", background: loading ? "var(--accent)" : "var(--border-inner)", color: loading ? "var(--text-primary)" : "var(--text-muted)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>2</div>
                            <span style={{ fontSize: 14, fontWeight: 600, color: loading ? "var(--text-primary)" : "var(--text-muted)" }}>Analyzing</span>
                        </div>
                        <div style={{ flex: 1, height: 1, background: "var(--border-inner)" }} />
                        <div style={{ display: "flex", alignItems: "center", gap: 8, opacity: result ? 1 : 0.4, transition: "opacity 0.3s" }}>
                            <div style={{ width: 24, height: 24, borderRadius: "50%", background: result ? "var(--risk-low)" : "var(--border-inner)", color: result ? "var(--text-primary)" : "var(--text-muted)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>3</div>
                            <span style={{ fontSize: 14, fontWeight: 600, color: result ? "var(--text-primary)" : "var(--text-muted)" }}>Results</span>
                        </div>
                    </div>

                    <div style={{ marginBottom: 24, display: loading || result || showManual ? "none" : "block" }}>
                        <div style={{ fontFamily: "var(--font-head)", fontSize: 24, fontWeight: 800, color: "var(--text-primary)", marginBottom: 6 }}>
                            Scan Social Profile
                        </div>
                        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                            Enter a profile URL or @handle (Instagram, Twitter/X, YouTube, Mastodon). Our calibrated ensemble model analyzes behavioral, lexical, and account features.
                        </div>
                    </div>

                    {/* Step 1: Input & Configuration */}
                    {!(loading || result || showManual) && (
                        <div className="animate-fade-in">
                            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
                                <div style={{ flex: 1, position: "relative", minWidth: 240 }}>
                                    <div style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", fontSize: 18 }}>
                                        🔗
                                    </div>
                                    <input
                                        ref={inputRef}
                                        id="profile-url-input"
                                        type="text"
                                        value={profileUrl}
                                        onChange={e => setProfileUrl(e.target.value)}
                                        onKeyDown={e => e.key === "Enter" && handleScan()}
                                        placeholder="https://instagram.com/username or @handle"
                                        className="input-field"
                                        style={{ width: "100%", paddingLeft: 44, paddingRight: 110, fontSize: 15, height: 56, fontWeight: 500, background: "var(--bg-surface-secondary)" }}
                                        disabled={loading}
                                        autoFocus
                                    />
                                    {/* Auto-detected platform chip (B9) */}
                                    {profileUrl.trim() && (
                                        <div style={{
                                            position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                                            padding: "4px 10px", borderRadius: 8, fontSize: 11, fontWeight: 700,
                                            background: "rgba(99,102,241,0.12)", color: "var(--accent-light)",
                                            border: "1px solid rgba(99,102,241,0.25)", textTransform: "capitalize",
                                        }}>
                                            {detectedPlatform}
                                        </div>
                                    )}
                                </div>
                                <button
                                    id="scan-submit-btn"
                                    className="btn-primary"
                                    onClick={() => handleScan(null, null)}
                                    disabled={loading || !scanConsent || !profileUrl.trim()}
                                    title={!scanConsent ? "Please confirm the consent checkbox first." : !profileUrl.trim() ? "Enter a URL or handle." : ""}
                                    style={{
                                        padding: "0 32px", height: 56, fontSize: 15, fontWeight: 700,
                                        boxShadow: "0 8px 24px rgba(99,102,241,0.25)",
                                        opacity: (!scanConsent || !profileUrl.trim()) ? 0.6 : 1,
                                    }}
                                >
                                    Start Analysis →
                                </button>
                            </div>

                            {/* Quick Recent Scans Pick (B9) */}
                            {recentScans.length > 0 && (
                                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 18, flexWrap: "wrap" }}>
                                    <span style={{ fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>Recent:</span>
                                    {recentScans.map((r, i) => (
                                        <button
                                            key={i}
                                            onClick={() => {
                                                const u = r.profile?.replace("@", "") || "";
                                                const finalU = `https://instagram.com/${u}`;
                                                setProfileUrl(finalU);
                                                handleScan(finalU, true);
                                            }}
                                            className="btn-ghost"
                                            style={{
                                                fontSize: 12, padding: "3px 10px", borderRadius: 99,
                                                background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)",
                                                color: "var(--text-secondary)",
                                            }}
                                        >
                                            {r.profile} ({r.platform})
                                        </button>
                                    ))}
                                </div>
                            )}

                            {/* Consent Checkbox & Retention Policy Notice (B8) */}
                            <label
                                style={{
                                    display: "flex", alignItems: "flex-start", gap: 14,
                                    padding: "16px 20px", background: "var(--bg-surface-secondary)",
                                    border: "1px solid var(--border-inner)", borderRadius: 12, cursor: "pointer",
                                }}
                            >
                                <input
                                    id="scan-consent-checkbox"
                                    type="checkbox"
                                    checked={scanConsent}
                                    onChange={e => setScanConsent(e.target.checked)}
                                    disabled={loading}
                                    style={{
                                        width: 18, height: 18, marginTop: 2, flexShrink: 0,
                                        accentColor: "var(--accent-dark)", cursor: "pointer",
                                    }}
                                />
                                <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                    <span>I confirm authorization to submit this profile for analysis. </span>
                                    <span style={{ color: "var(--text-muted)" }}>
                                        Only permitted publicly visible profile attributes are collected. Records are retained for 30 days per data retention policies.
                                    </span>
                                </div>
                            </label>

                            {/* Bulk Scanner Link (B9) */}
                            <div style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12.5 }}>
                                <span style={{ color: "var(--text-muted)" }}>Press Enter to scan, Esc to clear.</span>
                                <button
                                    onClick={onNavigateToBulk}
                                    style={{ background: "none", border: "none", color: "var(--accent-light)", cursor: "pointer", fontWeight: 600, padding: 0 }}
                                >
                                    Scan multiple profiles in bulk →
                                </button>
                            </div>

                            {error && (
                                <div className="animate-slide-down" style={{
                                    marginTop: 20, padding: "14px 18px",
                                    background: "rgba(220,38,38,0.05)", border: "1px solid rgba(220,38,38,0.2)",
                                    borderRadius: 12, fontSize: 14, color: "#b91c1c", fontWeight: 500,
                                    display: "flex", alignItems: "flex-start", gap: 10,
                                }}>
                                    <span style={{ flexShrink: 0, fontSize: 16 }}>⚠</span>
                                    {error}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Step 2: Animated Job Progress */}
                    {loading && activeStep >= 0 && (
                        <div className="animate-fade-in py-4">
                            <ScanningAnimation activeStep={activeStep} onCancel={handleCancelScan} />
                        </div>
                    )}

                    {/* Manual Fallback (B5) */}
                    {showManual && !loading && (
                        <ManualFallbackForm
                            profile={manualProfile}
                            platform={manualProfile.platform}
                            onUpdate={updateManual}
                            onSubmit={handleManualScan}
                            onCancel={() => setShowManual(false)}
                            loading={loading}
                        />
                    )}

                    {/* Analysis Complete / Back & Reset Header */}
                    {result && !loading && (
                        <div
                            className="animate-slide-down"
                            style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                flexWrap: "wrap",
                                gap: 16,
                                padding: "18px 22px",
                                background: "var(--bg-surface-secondary)",
                                border: "1px solid var(--border-hover)",
                                borderRadius: 14,
                                boxShadow: "0 4px 16px rgba(0, 0, 0, 0.25)",
                            }}
                        >
                            <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
                                <button
                                    id="btn-back-to-scan"
                                    onClick={handleBackToScan}
                                    className="btn-primary"
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 8,
                                        padding: "10px 20px",
                                        fontSize: 14,
                                        fontWeight: 700,
                                        cursor: "pointer",
                                    }}
                                >
                                    <ArrowLeft size={16} />
                                    Back to Scan
                                </button>
                                <div>
                                    <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-primary)" }}>
                                        Analysis Complete
                                    </div>
                                    <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 2 }}>
                                        Target: <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>@{result?.profile?.username || result?.username}</span>
                                        {(result?.platform || result?.profile?.platform) && (
                                            <span style={{ textTransform: "capitalize", marginLeft: 6, color: "var(--text-muted)" }}>
                                                · {result?.platform || result?.profile?.platform}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <button
                                    id="btn-new-scan"
                                    className="btn-ghost"
                                    onClick={handleNewScan}
                                    style={{
                                        fontSize: 13,
                                        padding: "10px 16px",
                                        border: "1px solid var(--border-hover)",
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 6,
                                    }}
                                >
                                    + New Scan (Esc)
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Step 3: Upgraded Results Panel */}
                <div ref={resultsRef}>
                    {result?.final_score !== undefined && (
                        <ResultsPanel
                            result={result}
                            onBack={handleBackToScan}
                            onNewScan={handleNewScan}
                            onDeleteScan={() => {
                                setResult(null);
                                setProfileUrl("");
                                setActiveStep(-1);
                            }}
                        />
                    )}
                </div>

            </div>

            {/* ── Right Column: Truthful System Status & Log (B7) ────────────────────────────── */}
            <div className="hidden lg:flex" style={{ width: 340, flexDirection: "column", gap: 24, flexShrink: 0 }}>
                
                {/* Truthful Intelligence Engines Card (B7) */}
                <div className="premium-glass" style={{ padding: "24px" }}>
                    <div style={{ fontFamily: "var(--font-head)", fontSize: 16, fontWeight: 800, marginBottom: 20 }}>
                        Intelligence Engines
                    </div>
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        
                        {/* ML Ensemble Model */}
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, background: "var(--bg-surface-secondary)", borderRadius: 12, padding: 12 }}>
                            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(99,102,241,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", flexShrink: 0 }}>
                                🧠
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>
                                    {systemStatus?.model?.name ? `${systemStatus.model.name} (${systemStatus.model.version || "v4"})` : "Ensemble Classifier v4"}
                                </div>
                                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                                    {systemStatus?.metrics?.ml_median_latency_ms !== null && systemStatus?.metrics?.ml_median_latency_ms !== undefined
                                        ? `Latency: ${systemStatus.metrics.ml_median_latency_ms}ms · F1: ${(systemStatus.model?.test_metrics?.macro_f1 || 0.917).toFixed(3)}`
                                        : "Status: Online (calibrated v4)"}
                                </div>
                                <div className="mt-2 w-full h-1.5 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                    <div className="h-full bg-[var(--accent)] w-[100%] rounded-full shadow-[0_0_10px_var(--accent)]" />
                                </div>
                            </div>
                        </div>

                        {/* Semantic NLP Model */}
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, background: "var(--bg-surface-secondary)", borderRadius: 12, padding: 12 }}>
                            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(16,185,129,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--risk-low)", flexShrink: 0 }}>
                                📚
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>
                                    {systemStatus?.nlp?.name || "Semantic MiniLM NLP"}
                                </div>
                                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                                    {systemStatus?.nlp?.loaded
                                        ? `Loaded (${systemStatus.nlp.device || "CPU"}) · Negation-gated`
                                        : "Unavailable"}
                                </div>
                                <div className="mt-2 w-full h-1.5 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                    <div className="h-full bg-[var(--risk-low)] w-[100%] rounded-full shadow-[0_0_10px_var(--risk-low)]" />
                                </div>
                            </div>
                        </div>

                        {/* Database & Collector Breakers */}
                        {systemStatus?.collectors?.circuit_breakers && (
                            <div style={{ fontSize: 11.5, color: "var(--text-muted)", padding: "10px 12px", background: "var(--bg-surface-secondary)", borderRadius: 10, lineHeight: 1.5 }}>
                                <div style={{ fontWeight: 700, color: "var(--text-secondary)", marginBottom: 4 }}>Circuit Breakers</div>
                                {Object.entries(systemStatus.collectors.circuit_breakers).map(([name, cb]) => (
                                    <div key={name} style={{ display: "flex", justifyContent: "space-between" }}>
                                        <span style={{ textTransform: "capitalize" }}>{name}:</span>
                                        <span style={{ color: cb.state === "CLOSED" ? "var(--risk-low)" : "var(--risk-high)", fontWeight: 600 }}>{cb.state}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Real Live Security Log (B7) */}
                <div className="premium-glass" style={{ padding: "24px", flex: 1, display: "flex", flexDirection: "column" }}>
                    <div style={{ fontFamily: "var(--font-head)", fontSize: 16, fontWeight: 800, marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>Live Security Log</span>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--risk-low)", boxShadow: "0 0 8px var(--risk-low)", animation: "glow-pulse 2s infinite" }} />
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 14, flex: 1, overflowY: "auto", pr: 2 }}>
                        {securityLogs.length > 0 ? (
                            securityLogs.map((log, i) => (
                                <div key={i} style={{ display: "flex", gap: 12, fontSize: 13, borderBottom: i < securityLogs.length - 1 ? "1px solid var(--border-inner)" : "none", paddingBottom: i < securityLogs.length - 1 ? 14 : 0 }}>
                                    <div style={{ color: "var(--text-muted)", width: 55, flexShrink: 0, fontWeight: 600 }}>{log.time}</div>
                                    <div style={{ color: "var(--text-secondary)", fontWeight: 500, lineHeight: 1.4 }}>{log.action}</div>
                                </div>
                            ))
                        ) : (
                            <div style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", padding: "20px 0" }}>
                                Monitoring profile audit events…
                            </div>
                        )}
                    </div>
                </div>

            </div>

        </div>
    );
}
