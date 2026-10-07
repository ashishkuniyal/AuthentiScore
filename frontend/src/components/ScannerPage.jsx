// ScannerPage.jsx — Automated URL-driven scan (primary flow) + manual fallback
import { useState, useRef, useEffect } from "react";
import ResultsPanel from "./ResultsPanel";
import {
    autoScan,
    profileScan,
} from "../services/api";

// ==============================================================
// Pipeline animation steps
// (single-request flow — steps are animated client-side for UX)
// ==============================================================

const PIPELINE_STEPS = [
    { id: "validate",  label: "Validating profile URL" },
    { id: "collect",   label: "Collecting permitted public data" },
    { id: "features",  label: "Extracting features" },
    { id: "ml",        label: "Running ML model" },
    { id: "nlp",       label: "Analysing bio with NLP" },
    { id: "risk",      label: "Calculating unified risk score" },
    { id: "shap",      label: "Generating SHAP explanation" },
    { id: "save",      label: "Saving result" },
];

// ==============================================================
// Collection source badge labels
// ==============================================================

const SOURCE_LABELS = {
    official_api:          "Official API",
    permitted_public_page: "Automated Public Collection",
    user_provided:         "User-Provided Fallback",
    none:                  "No Automated Source",
};

const SOURCE_COLORS = {
    official_api:          { bg: "rgba(5,150,105,0.08)",  border: "rgba(5,150,105,0.25)",  text: "var(--risk-low)" },
    permitted_public_page: { bg: "rgba(99,102,241,0.08)", border: "rgba(99,102,241,0.25)", text: "var(--accent)" },
    user_provided:         { bg: "rgba(217,119,6,0.08)",  border: "rgba(217,119,6,0.25)",  text: "var(--risk-med)" },
    none:                  { bg: "rgba(220,38,38,0.06)",  border: "rgba(220,38,38,0.18)",  text: "#b91c1c" },
};

// ==============================================================
// Scanning Animation
// ==============================================================

function ScanningAnimation({ activeStep }) {
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
        >
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
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
                        This usually takes a few seconds
                    </div>
                </div>
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
// Collection Source Badge
// ==============================================================

function CollectionBadge({ collection }) {
    if (!collection) return null;

    const source  = collection.source || "none";
    const status  = collection.status || "unknown";
    const fields  = collection.fields_collected || [];
    const label   = SOURCE_LABELS[source] || source;
    const colors  = SOURCE_COLORS[source] || SOURCE_COLORS.none;

    const statusIcon =
        status === "success" ? "✓" :
        status === "partial" ? "◑" : "✕";

    const statusColor =
        status === "success" ? "var(--risk-low)" :
        status === "partial" ? "var(--risk-med)" : "#b91c1c";

    return (
        <div
            style={{
                marginTop: 24,
                padding: "18px 22px",
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: 14,
            }}
        >
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 800, color: "var(--text-muted)" }}>
                    Data Source
                </div>
                <div style={{
                    display: "inline-flex", alignItems: "center", gap: 6,
                    padding: "4px 14px", borderRadius: 99,
                    background: colors.bg, border: `1px solid ${colors.border}`,
                    fontSize: 13, fontWeight: 700, color: colors.text,
                }}>
                    <span style={{ color: statusColor }}>{statusIcon}</span>
                    {label}
                </div>
                {fields.length > 0 && (
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                        Fields collected: {fields.join(", ")}
                    </div>
                )}
            </div>
            {status === "partial" && (
                <div style={{ marginTop: 10, fontSize: 13, color: "var(--risk-med)", fontWeight: 500 }}>
                    ◑ Partial collection — some fields were unavailable from the automated source.
                </div>
            )}
            {status === "failed" && (
                <div style={{ marginTop: 10, fontSize: 13, color: "#b91c1c", fontWeight: 500 }}>
                    ✕ Automated collection failed — result is based on user-provided data.
                </div>
            )}
        </div>
    );
}

// ==============================================================
// Manual Fallback Form
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
                    Automated data collection was incomplete for <strong>{platform}</strong>. Please enter the missing publicly visible information below to proceed.
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
                    <select value={profile.has_profile_picture ?? 1} onChange={e => onUpdate("has_profile_picture", Number(e.target.value))} className="input-field">
                        <option value={1}>Available</option>
                        <option value={0}>Missing</option>
                    </select>
                </div>
                <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>Account Privacy</label>
                    <select value={profile.is_private ?? 0} onChange={e => onUpdate("is_private", Number(e.target.value))} className="input-field">
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
                <button className="btn-primary" onClick={onSubmit} disabled={loading || !profile.username?.trim()}>
                    {loading ? "Analysing…" : "Run Analysis →"}
                </button>
            </div>
        </div>
    );
}

// ==============================================================
// Feature Cards
// ==============================================================

// Removed FeatureCards to reduce clutter
// ==============================================================
// Main ScannerPage
// ==============================================================

export default function ScannerPage({ notifications = [], initialSearchQuery = "", onClearSearch = () => {} }) {
    const [profileUrl,    setProfileUrl]    = useState("");
    const [scanConsent,   setScanConsent]   = useState(false);
    const [loading,       setLoading]       = useState(false);
    const [activeStep,    setActiveStep]    = useState(-1);
    const [error,         setError]         = useState("");
    const [result,        setResult]        = useState(null);
    const [showManual,    setShowManual]    = useState(false);
    const [manualProfile, setManualProfile] = useState({
        platform: "", profile_url: "", username: "",
        followers: 0, following: 0, posts: 0,
        bio: "", has_profile_picture: 1, is_private: 0,
    });
    const resultsRef = useRef(null);

    // Auto-trigger scan if global search query is passed
    useEffect(() => {
        if (initialSearchQuery) {
            let scanUrl = initialSearchQuery;
            if (!scanUrl.startsWith("http")) {
                scanUrl = `https://instagram.com/${scanUrl.replace('@', '')}`;
            }
            setProfileUrl(scanUrl);
            setScanConsent(true);
            onClearSearch();
            // Need to wrap in setTimeout because handleScan checks profileUrl state,
            // but we can just pass the url directly if we adjust handleScan.
            // Actually, we'll just trigger it directly here to bypass state latency.
            handleScan(scanUrl, true);
        }
    }, [initialSearchQuery]);

    // Provide default static logs, then prepend real ones
    const staticLogs = [
        { time: "Just now", action: "NLP Weights synced" },
        { time: "2m ago", action: "System boot sequence" }
    ];
    const liveLogs = notifications.map(n => ({
        time: "Just now", action: n.message
    }));
    const auditLogs = [...liveLogs, ...staticLogs].slice(0, 5);


    function updateManual(field, value) {
        setManualProfile(p => ({ ...p, [field]: value }));
    }

    // Animate through pipeline steps with a brief pause each
    async function step(n) {
        setActiveStep(n);
        return new Promise(r => setTimeout(r, 480));
    }

    // ----------------------------------------------------------
    // Primary: Automated scan
    // ----------------------------------------------------------

    async function handleScan(directUrl = null, directConsent = null) {
        const isUrlString = typeof directUrl === 'string';
        const checkConsent = (directConsent !== null && typeof directConsent === 'boolean') ? directConsent : scanConsent;
        const url = (isUrlString && directUrl) ? directUrl.trim() : profileUrl.trim();
        
        if (!checkConsent) { setError("Please confirm the scanning consent first."); return; }
        if (!url) { setError("Please enter a profile URL."); return; }

        setError(""); setResult(null); setShowManual(false);
        setLoading(true); setActiveStep(0);

        // Animate the first few steps while the single request runs
        const animateSteps = async () => {
            for (let i = 0; i < PIPELINE_STEPS.length; i++) {
                await step(i);
            }
        };

        try {
            // Run animation and API call concurrently.
            // The animation ensures the user sees progress;
            // the real request resolves when the backend finishes.
            const [scan] = await Promise.all([
                autoScan(url),
                animateSteps(),
            ]);

            const collectionStatus = scan?.collection?.status;

            if (collectionStatus === "success") {
                // Full automated collection succeeded — show results directly
                setResult(scan);
                setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);

            } else {
                // Partial or failed — pre-fill manual form with whatever was collected
                const platform = scan?.platform || "unknown";
                setManualProfile({
                    platform,
                    profile_url:         url,
                    username:            scan?.username || "",
                    followers:           scan?.features?.followers ?? 0,
                    following:           scan?.features?.following ?? 0,
                    posts:               scan?.features?.posts ?? 0,
                    bio:                 scan?.collected_bio || "",
                    has_profile_picture: scan?.features?.has_profile_picture ?? 1,
                    is_private:          scan?.features?.is_private ?? 0,
                });
                setShowManual(true);
            }

        } catch (err) {
            // Backend returned an error (e.g., unsupported platform, network issue)
            setError(err.message || "Unable to process this profile URL.");
        } finally {
            setLoading(false);
            setActiveStep(-1);
        }
    }

    // ----------------------------------------------------------
    // Fallback: Manual scan
    // ----------------------------------------------------------

    async function handleManualScan() {
        if (!scanConsent) { setError("Please confirm the scanning consent."); return; }
        if (!manualProfile.username.trim()) { setError("Please enter the profile username."); return; }

        setError(""); setResult(null);
        setLoading(true); setActiveStep(3);

        try {
            await step(3); await step(4); await step(5); await step(6); await step(7);
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
            // Tag result with user_provided collection metadata for the badge
            setResult({
                ...scan,
                collection: {
                    source:           "user_provided",
                    status:           "success",
                    timestamp:        new Date().toISOString(),
                    fields_collected: [],
                },
            });
            setShowManual(false);
            setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 200);
        } catch (err) {
            setError(err.message || "Unable to run the profile prediction.");
        } finally {
            setLoading(false);
            setActiveStep(-1);
        }
    }

    // ----------------------------------------------------------
    // Render
    // ----------------------------------------------------------

    return (
        <div style={{ display: "flex", gap: 32, padding: "32px", maxWidth: 1600, margin: "0 auto", height: "100%" }}>
            
            {/* ── Left Column: Scanner ────────────────────────────── */}
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 32, maxWidth: 860 }}>
                
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
                        <div style={{ display: "flex", alignItems: "center", gap: 8, opacity: (activeStep === -1 && !result && !showManual) ? 1 : 0.4, transition: "opacity 0.3s" }}>
                            <div style={{ width: 24, height: 24, borderRadius: "50%", background: "var(--accent)", color: "var(--text-primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700 }}>1</div>
                            <span style={{ fontSize: 14, fontWeight: 600 }}>Configure Scan</span>
                        </div>
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

                    <div style={{ marginBottom: 28, display: loading || result || showManual ? 'none' : 'block' }}>
                        <div style={{ fontFamily: "var(--font-head)", fontSize: 24, fontWeight: 800, color: "var(--text-primary)", marginBottom: 6 }}>
                            Enter Profile Details
                        </div>
                        <div style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                            Provide a public Instagram or Twitter URL. Our ensemble models will instantly fetch and assess the risk profile.
                        </div>
                    </div>

                    {/* Step 1: Input (Hide when scanning or showing results/manual) */}
                    {!(loading || result || showManual) && (
                        <div className="animate-fade-in">
                            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
                                <div style={{ flex: 1, position: "relative", minWidth: 240 }}>
                                    <div style={{ position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", fontSize: 18 }}>
                                        🔗
                                    </div>
                                    <input
                                        id="profile-url-input"
                                        type="url"
                                        value={profileUrl}
                                        onChange={e => setProfileUrl(e.target.value)}
                                        onKeyDown={e => e.key === "Enter" && handleScan()}
                                        placeholder="https://www.instagram.com/username/"
                                        className="input-field"
                                        style={{ width: "100%", paddingLeft: 44, fontSize: 15, height: 56, fontWeight: 500, background: "var(--bg-surface-secondary)" }}
                                        disabled={loading}
                                    />
                                </div>
                                <button
                                    id="scan-submit-btn"
                                    className="btn-primary"
                                    onClick={() => handleScan(null, null)}
                                    disabled={loading || !scanConsent}
                                    style={{ padding: "0 36px", height: 56, fontSize: 16, boxShadow: "0 8px 24px rgba(99,102,241,0.25)" }}
                                >
                                    Start Analysis →
                                </button>
                            </div>

                            <label
                                style={{
                                    display: "flex", alignItems: "flex-start", gap: 14,
                                    padding: "16px 20px", background: "var(--bg-surface-secondary)",
                                    border: "1px solid var(--border-inner)", borderRadius: 12, cursor: "pointer",
                                    transition: "background 0.2s, border-color 0.2s"
                                }}
                                onMouseEnter={e => e.currentTarget.style.borderColor = "var(--border-inner)"}
                                onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border-inner)"}
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
                                <span style={{ fontSize: 13.5, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                    I confirm I am authorised to submit this profile for analysis. Data will be processed in accordance with the strict AuthentiScore retention policy.
                                </span>
                            </label>

                            {error && (
                                <div className="animate-slide-down" style={{
                                    marginTop: 20, padding: "14px 18px",
                                    background: "rgba(220,38,38,0.05)",
                                    border: "1px solid rgba(220,38,38,0.2)",
                                    borderRadius: 12, fontSize: 14, color: "#b91c1c", fontWeight: 500,
                                    display: "flex", alignItems: "flex-start", gap: 10,
                                }}>
                                    <span style={{ flexShrink: 0, fontSize: 16 }}>⚠</span>
                                    {error}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Step 2: Animated States */}
                    {loading && activeStep >= 0 && (
                        <div className="animate-fade-in py-8">
                            <ScanningAnimation activeStep={activeStep} />
                        </div>
                    )}

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
                    
                    {/* Provide a "Reset" button when showing results so user can scan again without refreshing */}
                    {result && !loading && (
                        <div className="flex justify-between items-center bg-[var(--bg-surface-secondary)] border border-[var(--bg-surface-secondary)] p-4 rounded-xl animate-slide-down">
                            <div>
                                <div className="text-sm font-bold text-[var(--text-primary)]">Analysis Complete</div>
                                <div className="text-xs text-[var(--text-muted)] mt-1">Target: {result?.profile?.username || result?.username}</div>
                            </div>
                            <button className="btn-ghost text-sm px-4 py-2 border-[var(--border-inner)]" onClick={() => { setResult(null); setProfileUrl(""); setActiveStep(-1); }}>
                                + New Scan
                            </button>
                        </div>
                    )}
                </div>

                {/* Step 3: Results Panel */}
                <div ref={resultsRef}>
                    {result?.final_score !== undefined && (
                        <div className="animate-fade-in mt-2">
                            <CollectionBadge collection={result.collection} />
                            <div style={{ marginTop: 24 }}>
                                <ResultsPanel result={result} />
                            </div>
                        </div>
                    )}
                </div>

            </div>

            {/* ── Right Column: System Status ────────────────────────────── */}
            <div className="hidden lg:flex" style={{ width: 340, flexDirection: "column", gap: 24, flexShrink: 0 }}>
                
                {/* Active Engines Card */}
                <div className="premium-glass" style={{ padding: "24px" }}>
                    <div style={{ fontFamily: "var(--font-head)", fontSize: 16, fontWeight: 800, marginBottom: 20 }}>
                        Intelligence Engines
                    </div>
                    
                    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, p: 12, background: "var(--bg-surface-secondary)", borderRadius: 12, padding: 12 }}>
                            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(99,102,241,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", flexShrink: 0 }}>
                                🧠
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>Random Forest ML</div>
                                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>v2.4 Online (Latency: 12ms)</div>
                                <div className="mt-2 w-full h-1.5 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                    <div className="h-full bg-[var(--accent)] w-[100%] rounded-full shadow-[0_0_10px_var(--accent)]" />
                                </div>
                            </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, p: 12, background: "var(--bg-surface-secondary)", borderRadius: 12, padding: 12 }}>
                            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(16,185,129,0.1)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--risk-low)", flexShrink: 0 }}>
                                📚
                            </div>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>MiniLM-L6 Semantic NLP</div>
                                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>Transformer loaded (GPU)</div>
                                <div className="mt-2 w-full h-1.5 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                    <div className="h-full bg-[var(--risk-low)] w-[100%] rounded-full shadow-[0_0_10px_var(--risk-low)]" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Audit Log Card */}
                <div className="premium-glass" style={{ padding: "24px", flex: 1, display: "flex", flexDirection: "column" }}>
                    <div style={{ fontFamily: "var(--font-head)", fontSize: 16, fontWeight: 800, marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>Live Security Log</span>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--risk-low)", boxShadow: "0 0 8px var(--risk-low)", animation: "glow-pulse 2s infinite" }} />
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 14, flex: 1, overflowY: "auto", pr: 2 }}>
                        {auditLogs.map((log, i) => (
                            <div key={i} style={{ display: "flex", gap: 12, fontSize: 13, borderBottom: i < auditLogs.length - 1 ? "1px solid var(--bg-surface-secondary)" : "none", paddingBottom: i < auditLogs.length - 1 ? 14 : 0 }}>
                                <div style={{ color: "var(--text-muted)", width: 55, flexShrink: 0, fontWeight: 600 }}>{log.time}</div>
                                <div style={{ color: "var(--text-secondary)", fontWeight: 500, lineHeight: 1.4 }}>{log.action}</div>
                            </div>
                        ))}
                    </div>
                </div>

            </div>

        </div>
    );
}
