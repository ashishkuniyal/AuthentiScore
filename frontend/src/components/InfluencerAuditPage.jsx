import { useState, useRef, useEffect } from "react";
import { Upload, Users, ShieldAlert, FileText, CheckCircle, Search, Activity, Wifi, Loader2 } from "lucide-react";
import { toast } from "../utils/toast";
import { uploadInfluencerCsv, startLiveAudit, getInstagramSessionStatus } from "../services/api";
import { useNotifications } from "../context/useNotifications";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import ProfileDeepAuditModal from "./ProfileDeepAuditModal";

function StatCard({ label, value, sub, icon: Icon, color }) {
    return (
        <div className="bg-[var(--bg-card)] border border-[var(--border-inner)] rounded-2xl p-6 flex flex-col shadow-[var(--shadow-card)]">
            <div className="flex justify-between items-center mb-4">
                <span className="text-[var(--text-secondary)] font-bold text-xs uppercase tracking-wider">{label}</span>
                {Icon && <div className="p-2 rounded-lg" style={{ background: `${color}15`, color }}><Icon size={18} /></div>}
            </div>
            <div className="text-3xl font-extrabold text-[var(--text-primary)]">{value}</div>
            {sub && <div className="text-sm text-[var(--text-muted)] mt-2 font-medium">{sub}</div>}
        </div>
    );
}

const RISK_COLORS = {
    low: "var(--risk-low)",
    medium: "var(--risk-med)",
    high: "var(--risk-high)",
    very_high: "var(--risk-vhigh)"
};

export default function InfluencerAuditPage() {
    const { lastAuditMessage } = useNotifications();
    const [file, setFile] = useState(null);
    const [targetInfluencer, setTargetInfluencer] = useState("");
    const [isDragging, setIsDragging] = useState(false);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [auditMode, setAuditMode] = useState("csv");
    const [platform, setPlatform] = useState("instagram");
    const [sampleSize, setSampleSize] = useState(10);
    const [simulateFallback, setSimulateFallback] = useState(false);
    const [progress, setProgress] = useState(null);
    const [search, setSearch] = useState("");
    const [sessionStatus, setSessionStatus] = useState(null);
    const [selectedProfile, setSelectedProfile] = useState(null);
    const [currentAuditId, setCurrentAuditId] = useState(null);
    
    const fileInputRef = useRef(null);

    useEffect(() => {
        if (!lastAuditMessage) return;
        if (currentAuditId && lastAuditMessage.audit_id && lastAuditMessage.audit_id !== currentAuditId) {
            return;
        }

        const timer = setTimeout(() => {
            if (lastAuditMessage.type === "AUDIT_PROGRESS") {
                setProgress({
                    current: lastAuditMessage.current,
                    total: lastAuditMessage.total,
                    percentage: lastAuditMessage.percentage,
                    latest: lastAuditMessage.latest_profile
                });
            } else if (lastAuditMessage.type === "AUDIT_COMPLETE") {
                setResult(lastAuditMessage.final_result);
                setProgress(null);
                setLoading(false);
                toast("Live audit completed!", "success");
            } else if (lastAuditMessage.type === "AUDIT_ERROR") {
                setProgress(null);
                setLoading(false);
                toast(lastAuditMessage.message || "An error occurred during live audit.", "error");
            }
        }, 0);

        return () => clearTimeout(timer);
    }, [lastAuditMessage, currentAuditId]);

    useEffect(() => {
        if (platform !== "instagram" || auditMode !== "live") return;
        let isCancelled = false;
        getInstagramSessionStatus().then(res => {
            if (!isCancelled) setSessionStatus(res);
        }).catch(() => {
            if (!isCancelled) setSessionStatus({ status: "unknown", message: "Could not verify session" });
        });
        return () => { isCancelled = true; };
    }, [platform, auditMode]);



    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        const dropped = e.dataTransfer.files[0];
        if (dropped && dropped.type === "text/csv") {
            setFile(dropped);
        } else {
            toast("Please drop a valid CSV file.", "error");
        }
    };

    const handleFileSelect = (e) => {
        const selected = e.target.files[0];
        if (selected && selected.type === "text/csv") {
            setFile(selected);
        } else {
            toast("Please select a valid CSV file.", "error");
        }
    };

    const handleUpload = async () => {
        if (!file) {
            toast("Please select a CSV file first.", "error");
            return;
        }

        setLoading(true);
        try {
            const data = await uploadInfluencerCsv(file, targetInfluencer || "Unknown");
            setResult(data);
            toast("Audit completed successfully!", "success");
        } catch (err) {
            toast(err.message, "error");
        } finally {
            if (auditMode === "csv") setLoading(false);
        }
    };
    
    const handleLiveUpload = async () => {
        if (!targetInfluencer) {
            toast("Please provide an influencer username to scan.", "error");
            return;
        }
        
        setLoading(true);
        try {
            const data = await startLiveAudit(targetInfluencer, platform, sampleSize, simulateFallback);
            if (data?.audit_id) {
                setCurrentAuditId(data.audit_id);
            }
            toast("Live sampling started... Connecting to stream.", "success");
        } catch (err) {
            toast(err.message || "Failed to start live audit", "error");
            setLoading(false);
        }
    };


    const reset = () => {
        setFile(null);
        setResult(null);
        setTargetInfluencer("");
    };

    if (result) {
        const pieData = Object.entries(result.risk_breakdown).map(([k, v]) => ({
            name: k,
            value: v
        })).filter(d => d.value > 0);

        const filteredFollowers = result.followers_data.filter(f => 
            f.identifier.toLowerCase().includes(search.toLowerCase())
        );

        const fakePctColor = result.fake_percentage < 30 ? "var(--risk-low)" : (result.fake_percentage < 60 ? "var(--risk-med)" : "var(--risk-high)");

        return (
            <main className="p-10 max-w-[1200px] mx-auto animate-fade-in w-full box-border">
                <div className="flex justify-between items-end mb-8 flex-wrap gap-4">
                    <div>
                        <div className="text-[var(--accent)] font-bold text-xs uppercase tracking-widest mb-2">Audit Complete</div>
                        <h1 className="text-[32px] font-extrabold tracking-tight">Influencer Follower Fraud Audit</h1>
                        <p className="text-[var(--text-secondary)] text-sm mt-1">Audit ID: <span className="font-mono">{result.audit_id}</span></p>
                    </div>
                    <div className="flex gap-3">
                        <button className="btn-ghost px-4 py-2" onClick={reset}>New Audit</button>
                        <button className="btn-primary flex items-center gap-2" onClick={() => window.print()}>
                            <FileText size={16} /> Export PDF
                        </button>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <div className="section-card md:col-span-1 flex flex-col items-center justify-center p-8 bg-gradient-to-b from-[var(--bg-card)] to-[var(--bg-surface)]">
                        <div className="text-[var(--text-muted)] font-bold uppercase tracking-wider text-sm mb-4">Fake Follower Estimate</div>
                        <div className="text-6xl font-black mb-2" style={{ color: fakePctColor }}>
                            {result.fake_percentage}%
                        </div>
                        {result.ci_lower !== undefined && (
                            <div className="text-sm font-semibold mb-2" style={{ color: fakePctColor }}>
                                95% CI: [{result.ci_lower}%, {result.ci_upper}%]
                            </div>
                        )}
                        <div className="text-[var(--text-secondary)] text-sm font-medium mb-4">
                            Scored {result.valid_scans !== undefined ? result.valid_scans : result.successful_scans} of {result.sample_size} sampled
                        </div>
                        {result.collection_success_rate !== undefined && (
                            <div className="text-xs px-3 py-1 rounded bg-[var(--bg-surface-secondary)] text-[var(--text-muted)] border border-[var(--border-inner)]">
                                Collection Success: <span className="font-bold text-[var(--text-primary)]">{result.collection_success_rate}%</span>
                            </div>
                        )}
                    </div>
                    
                    <div className="md:col-span-2 grid grid-cols-2 gap-6">
                        <StatCard label="Target Influencer" value={result.target_influencer} icon={Users} color="#8b5cf6" />
                        <StatCard label="Sample Size" value={result.sample_size} sub={`${result.successful_scans} Profiles successfully scanned`} icon={CheckCircle} color="#10b981" />
                        
                        {result.budget_warning && (
                            <div className="col-span-2 section-card bg-orange-900/20 border-orange-500/30 p-4">
                                <div className="text-sm font-bold text-orange-400">{result.budget_warning}</div>
                            </div>
                        )}
                        
                        <div className="col-span-2 section-card p-6">
                            <h3 className="font-bold mb-4 flex items-center gap-2"><ShieldAlert size={18} className="text-[var(--accent)]"/> Top Red Flags</h3>
                            <div className="flex flex-wrap gap-3">
                                {result.top_red_flags.map((flag, i) => (
                                    <div key={i} className="bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] px-3 py-1.5 rounded-full flex items-center gap-2">
                                        <span className="text-[var(--text-primary)] font-semibold text-sm">{flag.flag.replace(/_/g, ' ')}</span>
                                        <span className="bg-[var(--accent)] text-white text-xs px-2 py-0.5 rounded-full">{flag.count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
                
                <div className="mb-8 section-card p-4 bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                    <p className="text-sm text-[var(--text-muted)] font-medium">
                        <strong>Disclaimer:</strong> Follower lists obtained via API or scraping are often heavily biased by the platform's algorithms (e.g., returning recent followers or engaged followers rather than a true random sample). Results should be interpreted as an estimate.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="section-card lg:col-span-1 h-[400px] flex flex-col">
                        <h3 className="font-bold mb-4">Risk Breakdown</h3>
                        <div className="flex-1 relative">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={5} dataKey="value">
                                        {pieData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={RISK_COLORS[entry.name]} />
                                        ))}
                                    </Pie>
                                    <Tooltip 
                                        contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border-inner)", borderRadius: "8px" }}
                                        formatter={(value, name) => [value, name.toUpperCase()]}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                <span className="text-3xl font-black">{result.sample_size}</span>
                                <span className="text-[10px] uppercase font-bold text-[var(--text-muted)]">Scanned</span>
                            </div>
                        </div>
                    </div>

                    <div className="section-card lg:col-span-2 flex flex-col h-[400px]">
                        <div className="flex justify-between items-center mb-4 gap-4">
                            <h3 className="font-bold">Follower Sample Results</h3>
                            <div className="relative">
                                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                                <input 
                                    type="text" 
                                    placeholder="Search username..." 
                                    value={search}
                                    onChange={e => setSearch(e.target.value)}
                                    className="input-field text-sm py-1.5 pl-8 w-48"
                                />
                            </div>
                        </div>
                        <div className="flex-1 overflow-auto -mx-2 px-2">
                            <table className="w-full text-left border-collapse">
                                <thead className="sticky top-0 bg-[var(--bg-card)]">
                                    <tr className="border-b border-[var(--border-inner)]">
                                        <th className="py-3 px-2 text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">Username/URL</th>
                                        <th className="py-3 px-2 text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">Platform</th>
                                        <th className="py-3 px-2 text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">Score</th>
                                        <th className="py-3 px-2 text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">Classification</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredFollowers.map((f, i) => (
                                        <tr key={i} className={`border-b border-[var(--bg-surface-secondary)] transition-colors ${f.status === 'collection_failed' ? 'opacity-40 grayscale hover:bg-transparent' : 'hover:bg-[var(--bg-surface-secondary)]'}`}>
                                            <td className="py-3 px-2 font-semibold text-sm">
                                                {f.identifier}
                                                {f.status === 'collection_failed' && <span className="ml-2 text-[10px] bg-red-900/40 text-red-400 px-1.5 py-0.5 rounded">UNAVAILABLE</span>}
                                                {f.is_mocked && <span className="ml-2 text-[10px] font-bold bg-orange-900/50 text-orange-400 border border-orange-500/30 px-1.5 py-0.5 rounded">SIMULATED</span>}
                                            </td>
                                            <td className="py-3 px-2 text-sm text-[var(--text-secondary)] capitalize">{f.platform}</td>
                                            <td className="py-3 px-2 font-mono text-sm font-bold" style={{ color: f.status === 'collection_failed' ? 'inherit' : (f.score >= 60 ? "var(--risk-high)" : "var(--risk-low)") }}>
                                                {f.status === 'collection_failed' ? '---' : f.score.toFixed(1)}
                                            </td>
                                            <td className="py-3 px-2">
                                                {f.status === 'collection_failed' ? (
                                                    <span className="text-xs font-bold px-2 py-1 rounded-full uppercase bg-[var(--bg-surface-secondary)] text-[var(--text-muted)] border border-[var(--border-inner)]">
                                                        Failed Scan
                                                    </span>
                                                ) : (
                                                    <span className="text-xs font-bold px-2 py-1 rounded-full uppercase" style={{ 
                                                        background: `${RISK_COLORS[f.classification]}22`, 
                                                        color: RISK_COLORS[f.classification],
                                                        border: `1px solid ${RISK_COLORS[f.classification]}44`
                                                    }}>
                                                        {f.classification.replace('_', ' ')}
                                                    </span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                    {filteredFollowers.length === 0 && (
                                        <tr>
                                            <td colSpan={4} className="text-center py-8 text-[var(--text-muted)] text-sm">No followers found.</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        );
    }

    return (
        <main className="p-10 max-w-[800px] mx-auto w-full box-border animate-fade-in flex flex-col items-center justify-center min-h-[80vh]">
            <div className="text-center mb-10">
                <h1 className="text-[40px] font-black tracking-tight mb-4">Influencer Follower Audit</h1>
                <p className="text-[var(--text-secondary)] text-lg max-w-[600px] mx-auto">
                    Upload a CSV containing a random sample of an influencer's followers (single column with a header) to generate an aggregate fraud analysis.
                </p>
            </div>

            <div className="w-full section-card flex flex-col gap-6">
                
                <div className="flex gap-2 p-1 bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] rounded-xl w-full max-w-xs mx-auto mb-2">
                    <button 
                        className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all ${auditMode === 'csv' ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                        onClick={() => setAuditMode('csv')}
                    >
                        CSV Upload
                    </button>
                    <button 
                        className={`flex-1 py-2 text-sm font-bold rounded-lg transition-all flex items-center justify-center gap-2 ${auditMode === 'live' ? 'bg-[var(--accent)] text-white shadow-[0_0_15px_rgba(99,102,241,0.3)]' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}
                        onClick={() => setAuditMode('live')}
                    >
                        <Wifi size={14} /> Live Sample
                    </button>
                </div>

                {auditMode === "live" ? (
                    <>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-bold text-[var(--text-secondary)] mb-2">Target Influencer</label>
                                <input 
                                    type="text" 
                                    value={targetInfluencer}
                                    onChange={(e) => setTargetInfluencer(e.target.value)}
                                    placeholder="e.g. cristiano" 
                                    className="input-field"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-bold text-[var(--text-secondary)] mb-2 flex items-center justify-between">
                                    <span>Platform</span>
                                    {sessionStatus && platform === "instagram" && (
                                        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full" 
                                            style={{
                                                background: sessionStatus.status === 'valid' ? 'rgba(16,185,129,0.1)' : sessionStatus.status === 'checking' ? 'rgba(139,92,246,0.1)' : 'rgba(239,68,68,0.1)',
                                                color: sessionStatus.status === 'valid' ? '#10b981' : sessionStatus.status === 'checking' ? '#8b5cf6' : '#ef4444',
                                                border: `1px solid ${sessionStatus.status === 'valid' ? 'rgba(16,185,129,0.2)' : sessionStatus.status === 'checking' ? 'rgba(139,92,246,0.2)' : 'rgba(239,68,68,0.2)'}`
                                            }}
                                            title={sessionStatus.message}
                                        >
                                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: sessionStatus.status === 'valid' ? '#10b981' : sessionStatus.status === 'checking' ? '#8b5cf6' : '#ef4444' }}></div>
                                            {sessionStatus.status}
                                        </div>
                                    )}
                                </label>
                                <select 
                                    value={platform}
                                    onChange={(e) => setPlatform(e.target.value)}
                                    className="input-field appearance-none bg-[var(--bg-surface)] text-[var(--text-primary)]"
                                >
                                    <option value="instagram">Instagram (Auth Required)</option>
                                    <option value="twitter">Twitter / X</option>
                                    <option value="github">GitHub</option>
                                    <option value="mastodon">Mastodon (mastodon.social)</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-bold text-[var(--text-secondary)] mb-2 flex justify-between">
                                Sample Size
                                <span className="text-[var(--accent)]">{sampleSize} Followers</span>
                            </label>
                            <input 
                                type="range" 
                                min="10" 
                                max={platform === "instagram" ? 50 : 100} 
                                step="10"
                                value={Math.min(sampleSize, platform === "instagram" ? 50 : 100)}
                                onChange={(e) => setSampleSize(parseInt(e.target.value))}
                                className="w-full accent-[var(--accent)]"
                            />
                            <div className="flex justify-between text-xs text-[var(--text-muted)] mt-2">
                                <span>Fast (10)</span>
                                <span>Thorough ({platform === "instagram" ? "50" : "100"})</span>
                            </div>
                        </div>
                        
                        <div className="flex items-center mt-2 bg-[var(--bg-surface-secondary)] p-3 rounded-lg border border-[var(--bg-surface-secondary)]">
                            <input 
                                type="checkbox"
                                id="simulateFallback"
                                checked={simulateFallback}
                                onChange={(e) => setSimulateFallback(e.target.checked)}
                                className="mr-3 w-4 h-4 accent-orange-500"
                            />
                            <label htmlFor="simulateFallback" className="text-sm text-[var(--text-secondary)] cursor-pointer">
                                <strong className="text-orange-400 block mb-0.5">Demo Mode: Allow Simulated Data</strong>
                                If a platform API blocks the request, automatically generate mock data to demonstrate the UI instead of failing.
                            </label>
                        </div>
                        
                        {progress && (
                            <div className="bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)] rounded-xl p-6 mt-2 relative overflow-hidden">
                                <div className="absolute top-0 left-0 h-1 bg-[var(--accent)] transition-all duration-300" style={{ width: `${progress.percentage}%` }}></div>
                                <div className="flex justify-between items-center mb-4">
                                    <div className="flex items-center gap-2 text-[var(--text-primary)] font-bold">
                                        <Loader2 size={16} className="animate-spin text-[var(--accent)]" /> 
                                        Live Sampling...
                                    </div>
                                    <div className="text-sm font-mono text-[var(--text-secondary)]">{progress.current} / {progress.total}</div>
                                </div>
                                <div className="w-full bg-[var(--bg-surface-secondary)] h-3 rounded-full mb-4 overflow-hidden">
                                    <div className="h-full bg-[var(--accent)] rounded-full transition-all duration-300" style={{ width: `${progress.percentage}%` }}></div>
                                </div>
                                {progress.latest && (
                                    <div className="flex items-center justify-between text-sm py-2 px-3 bg-[var(--bg-surface-secondary)] rounded-lg">
                                        <span className="font-semibold">@{progress.latest.identifier}</span>
                                        <span className="font-mono text-xs px-2 py-1 rounded" style={{
                                            background: progress.latest.score >= 60 ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
                                            color: progress.latest.score >= 60 ? 'var(--risk-high)' : 'var(--risk-low)'
                                        }}>
                                            {progress.latest.score} ({progress.latest.classification})
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                        
                        {!progress && (
                            <button 
                                className="btn-primary w-full py-4 text-lg mt-4 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                disabled={!targetInfluencer || loading}
                                onClick={handleLiveUpload}
                            >
                                {loading ? <><Loader2 size={20} className="animate-spin"/> Connecting...</> : <><Activity size={20}/> Start Live Audit</>}
                            </button>
                        )}
                    </>
                ) : (
                    <>
                        <div>
                            <label className="block text-sm font-bold text-[var(--text-secondary)] mb-2">Target Influencer (Optional)</label>
                            <input 
                                type="text" 
                                value={targetInfluencer}
                                onChange={(e) => setTargetInfluencer(e.target.value)}
                                placeholder="e.g. @cristiano" 
                                className="input-field"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-bold text-[var(--text-secondary)] mb-2">Follower List (CSV)</label>
                            <div 
                                className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center transition-all ${isDragging ? 'border-[var(--accent)] bg-[rgba(99,102,241,0.05)]' : 'border-[var(--border-inner)] bg-[var(--bg-surface-secondary)]'} ${file ? 'border-[var(--risk-low)] bg-[rgba(16,185,129,0.05)]' : ''}`}
                                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                                onDragLeave={() => setIsDragging(false)}
                                onDrop={handleDrop}
                            >
                                {file ? (
                                    <>
                                        <div className="w-12 h-12 bg-[var(--risk-low)] text-white rounded-full flex items-center justify-center mb-4 shadow-[0_0_15px_rgba(16,185,129,0.4)]">
                                            <CheckCircle size={24} />
                                        </div>
                                        <div className="font-bold text-lg">{file.name}</div>
                                        <div className="text-[var(--text-secondary)] text-sm mt-1">{(file.size / 1024).toFixed(1)} KB</div>
                                        <button className="mt-4 text-[var(--accent)] hover:underline text-sm font-semibold cursor-pointer bg-transparent border-none" onClick={() => setFile(null)}>Remove file</button>
                                    </>
                                ) : (
                                    <>
                                        <div className="w-16 h-16 bg-[var(--bg-surface-secondary)] text-[var(--text-secondary)] rounded-full flex items-center justify-center mb-4">
                                            <Upload size={28} />
                                        </div>
                                        <div className="font-bold text-lg mb-2">Drag and drop your CSV here</div>
                                        <div className="text-[var(--text-secondary)] text-sm mb-6">Must be a single column with a header row</div>
                                        <button className="btn-ghost" onClick={() => fileInputRef.current?.click()}>
                                            Browse Files
                                        </button>
                                        <input type="file" accept=".csv" className="hidden" ref={fileInputRef} onChange={handleFileSelect} />
                                    </>
                                )}
                            </div>
                        </div>

                        <button 
                            className="btn-primary w-full py-4 text-lg mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={!file || loading}
                            onClick={handleUpload}
                        >
                            {loading ? "Processing Audit (This may take a while)..." : "Run Audience Audit"}
                        </button>
                    </>
                )}
            </div>

            {/* Profile Deep Audit Modal */}
            <ProfileDeepAuditModal 
                profile={selectedProfile} 
                onClose={() => setSelectedProfile(null)} 
            />
        </main>
    );
}
