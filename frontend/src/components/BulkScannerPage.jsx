import { useState, useEffect } from "react";
import { Filter, Download, Upload, CheckCircle2, XCircle, ChevronRight } from "lucide-react";

function getRiskColor(score) {
    const s = Number(score ?? 0);
    if (s < 30) return "var(--risk-low)";
    if (s < 60) return "var(--risk-med)";
    if (s < 80) return "var(--risk-high)";
    return "var(--risk-vhigh)";
}

export default function BulkScannerPage() {
    const [file, setFile] = useState(null);
    const [jobId, setJobId] = useState(null);
    const [jobStatus, setJobStatus] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [error, setError] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [filter, setFilter] = useState("all");

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setError(null);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const startBulkScan = async () => {
        if (!file) {
            setError("Please select a CSV file first.");
            return;
        }
        
        setIsUploading(true);
        setError(null);
        
        const formData = new FormData();
        formData.append("file", file);
        
        try {
            const res = await fetch("http://localhost:8000/bulk/upload", {
                method: "POST",
                body: formData,
            });
            
            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Failed to start bulk scan");
            }
            
            const data = await res.json();
            setJobId(data.job_id);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsUploading(false);
        }
    };

    useEffect(() => {
        if (!jobId) return;
        
        const pollTimer = setInterval(async () => {
            try {
                const res = await fetch(`http://localhost:8000/bulk/${jobId}`);
                if (res.ok) {
                    const data = await res.json();
                    setJobStatus(data);
                    
                    if (data.status === "completed") {
                        clearInterval(pollTimer);
                    }
                }
            } catch (e) {
                console.error("Polling error:", e);
            }
        }, 2000);
        
        return () => clearInterval(pollTimer);
    }, [jobId]);

    const downloadCsv = () => {
        if (!jobStatus || !jobStatus.results) return;
        
        const headers = ["URL", "Status", "Score", "Classification", "Error"];
        const rows = jobStatus.results.map(r => [
            r.url, 
            r.status, 
            r.score !== undefined ? r.score : "", 
            r.classification || "", 
            r.error || ""
        ]);
        
        const csvContent = [
            headers.join(","),
            ...rows.map(e => e.map(item => `"${String(item).replace(/"/g, '""')}"`).join(","))
        ].join("\n");
        
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", `authentiscore_bulk_${jobId.substring(0, 8)}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const FILTERS = [
        { id: "all", label: "All Results" },
        { id: "high_risk", label: "High Risk (>= 60)" },
        { id: "low_risk", label: "Low Risk (< 60)" },
        { id: "failed", label: "Failed Scans" },
    ];

    const filteredResults = jobStatus?.results?.filter(r => {
        if (filter === "all") return true;
        if (filter === "high_risk") return r.status === "success" && Number(r.score ?? 0) >= 60;
        if (filter === "low_risk") return r.status === "success" && Number(r.score ?? 0) < 60;
        if (filter === "failed") return r.status !== "success";
        return true;
    }) || [];

    return (
        <div className="animate-fade-in" style={{ maxWidth: 1000, margin: "40px auto", padding: "0 24px", paddingBottom: 100, position: "relative" }}>
            <div className="absolute top-[10%] left-[-10%] w-[50%] h-[50%] bg-[var(--accent)] opacity-[0.03] blur-[120px] pointer-events-none rounded-full" />
            
            <div style={{ textAlign: "center", marginBottom: 40, position: "relative", zIndex: 10 }}>
                <h1 style={{ fontFamily: "var(--font-head)", fontSize: 36, fontWeight: 900, color: "var(--text-primary)", letterSpacing: "-0.02em", marginBottom: 12 }}>
                    Enterprise Bulk Scanning
                </h1>
                <p style={{ fontSize: 16, color: "var(--text-secondary)", maxWidth: 500, margin: "0 auto", lineHeight: 1.6 }}>
                    Upload a CSV of social media profile URLs. AuthentiScore will scan them all and generate a unified risk report in real-time.
                </p>
            </div>

            {!jobId ? (
                <div className="premium-glass animate-slide-up" style={{ padding: "48px 40px", textAlign: "center", maxWidth: 600, margin: "0 auto", position: "relative", zIndex: 10 }}>
                    <div 
                        onDrop={handleDrop}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        style={{
                            border: `2px dashed ${isDragging ? "var(--accent)" : "var(--border-inner)"}`,
                            borderRadius: 16,
                            padding: "60px 20px",
                            backgroundColor: isDragging ? "rgba(99,102,241,0.05)" : "var(--bg-surface-secondary)",
                            transition: "all 0.2s ease",
                            marginBottom: 24,
                            cursor: "pointer",
                            position: "relative"
                        }}
                        onClick={() => document.getElementById("csv-upload").click()}
                    >
                        <input 
                            type="file" 
                            accept=".csv"
                            onChange={handleFileChange}
                            style={{ display: "none" }}
                            id="csv-upload"
                        />
                        
                        <div style={{ display: "flex", justifyContent: "center", marginBottom: 16, opacity: isDragging ? 1 : 0.7, transition: "opacity 0.2s", color: "var(--accent-light)" }}>
                            <Upload size={48} />
                        </div>
                        
                        {file ? (
                            <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: 18 }}>
                                {file.name}
                            </div>
                        ) : (
                            <div>
                                <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: 18, marginBottom: 8 }}>
                                    Click to browse or drag CSV here
                                </div>
                                <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
                                    One URL per line. No headers required. Max 1,000 URLs.
                                </div>
                            </div>
                        )}
                    </div>
                    
                    {error && (
                        <div style={{ 
                            background: "rgba(220, 38, 38, 0.08)", 
                            color: "var(--risk-vhigh)", 
                            border: "1px solid rgba(220, 38, 38, 0.2)",
                            padding: "12px 16px", 
                            borderRadius: 8, 
                            fontWeight: 600,
                            marginBottom: 24,
                            fontSize: 14
                        }}>
                            {error}
                        </div>
                    )}
                    
                    <button
                        onClick={startBulkScan}
                        disabled={!file || isUploading}
                        className="btn-primary"
                        style={{ 
                            width: "100%", 
                            height: 54,
                            fontSize: 16,
                            opacity: !file || isUploading ? 0.6 : 1,
                            transform: !file || isUploading ? "none" : undefined,
                            boxShadow: "0 8px 24px rgba(99,102,241,0.25)"
                        }}
                    >
                        {isUploading ? "Uploading & Initializing..." : "Start Bulk Scan"}
                    </button>
                </div>
            ) : (
                <div className="animate-slide-up" style={{ position: "relative", zIndex: 10 }}>
                    <div className="premium-glass" style={{ padding: "40px", marginBottom: 24 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 30, flexWrap: "wrap", gap: 16 }}>
                            <div>
                                <h2 style={{ fontFamily: "var(--font-head)", fontSize: 24, fontWeight: 800, color: "var(--text-primary)", margin: "0 0 8px 0" }}>
                                    {jobStatus?.status === "completed" ? "Scan Complete" : "Scanning in Progress..."}
                                </h2>
                                <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 15 }}>
                                    Job ID: <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, background: "var(--bg-surface-secondary)", padding: "2px 6px", borderRadius: 4 }}>{jobId}</span>
                                </p>
                            </div>
                            {jobStatus?.status === "completed" && (
                                <button onClick={downloadCsv} className="btn-ghost border-[var(--border-inner)] flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-[var(--border-inner)]">
                                    <Download size={16} /> Download CSV Report
                                </button>
                            )}
                        </div>

                        {jobStatus ? (
                            <>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, fontWeight: 600, fontSize: 15 }}>
                                    <span style={{ color: "var(--text-primary)" }}>
                                        {jobStatus.completed + jobStatus.failed} / {jobStatus.total} Processed
                                    </span>
                                    <span style={{ color: "var(--accent-light)" }}>
                                        {jobStatus.total > 0 ? Math.round(((jobStatus.completed + jobStatus.failed) / jobStatus.total) * 100) : 0}%
                                    </span>
                                </div>
                                
                                <div style={{ 
                                    height: 14, 
                                    background: "var(--bg-surface-secondary)", 
                                    borderRadius: 99, 
                                    overflow: "hidden", 
                                    marginBottom: 32,
                                    boxShadow: "inset 0 1px 2px var(--bg-surface-secondary)"
                                }}>
                                    <div style={{ 
                                        height: "100%", 
                                        background: jobStatus.status === "completed" ? "var(--risk-low)" : "linear-gradient(90deg, var(--accent), #d946ef)",
                                        width: `${jobStatus.total > 0 ? ((jobStatus.completed + jobStatus.failed) / jobStatus.total) * 100 : 0}%`,
                                        transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                                        position: "relative"
                                    }}>
                                        {jobStatus.status !== "completed" && (
                                            <div style={{
                                                position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
                                                background: "linear-gradient(90deg, transparent, var(--text-muted), transparent)",
                                                animation: "shimmer 1.5s infinite linear",
                                                transform: "skewX(-20deg)"
                                            }} />
                                        )}
                                    </div>
                                </div>
                                
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                                    <div style={{ 
                                        background: "rgba(16, 185, 129, 0.05)", 
                                        border: "1px solid rgba(16, 185, 129, 0.15)",
                                        borderRadius: 12, padding: "20px", textAlign: "center"
                                    }}>
                                        <div style={{ fontSize: 36, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--risk-low)", lineHeight: 1 }}>
                                            {jobStatus.completed}
                                        </div>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", marginTop: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                            Successful Scans
                                        </div>
                                    </div>
                                    <div style={{ 
                                        background: "rgba(239, 68, 68, 0.05)", 
                                        border: "1px solid rgba(239, 68, 68, 0.15)",
                                        borderRadius: 12, padding: "20px", textAlign: "center"
                                    }}>
                                        <div style={{ fontSize: 36, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--risk-high)", lineHeight: 1 }}>
                                            {jobStatus.failed}
                                        </div>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", marginTop: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                            Failed Scans
                                        </div>
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)", fontWeight: 500 }}>
                                Initializing bulk analysis engine...
                            </div>
                        )}
                    </div>

                    {/* Results Table & Filters */}
                    {jobStatus?.results?.length > 0 && (
                        <>
                            {/* Global Filter System */}
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, overflowX: "auto", paddingBottom: 8 }} className="scrollbar-hide">
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

                            <div className="premium-glass animate-slide-up" style={{ padding: 0, overflow: "hidden", animationDelay: "0.1s" }}>
                                <div style={{ overflowX: "auto" }}>
                                    <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", minWidth: 600 }}>
                                        <thead>
                                            <tr style={{ background: "var(--bg-surface-secondary)", borderBottom: "1px solid var(--border-inner)" }}>
                                                <th style={{ padding: "16px 24px", fontSize: 11.5, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Target Profile</th>
                                                <th style={{ padding: "16px 24px", fontSize: 11.5, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Status</th>
                                                <th style={{ padding: "16px 24px", fontSize: 11.5, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Risk Score</th>
                                                <th style={{ padding: "16px 24px", fontSize: 11.5, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Classification</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {filteredResults.length > 0 ? filteredResults.map((r, i) => (
                                                <tr key={i} className="hover:bg-[var(--bg-surface-secondary)] transition-colors" style={{ borderBottom: "1px solid var(--border-inner)" }}>
                                                    <td style={{ padding: "16px 24px", maxWidth: 300, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                                        <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent-light)", textDecoration: "none", fontWeight: 600 }}>
                                                            {r.url.replace(/^https?:\/\/(www\.)?/, '')}
                                                        </a>
                                                        {r.error && (
                                                            <div style={{ fontSize: 12, color: "var(--risk-vhigh)", marginTop: 4, whiteSpace: "normal" }}>
                                                                {r.error}
                                                            </div>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: "16px 24px" }}>
                                                        {r.status === "success" ? (
                                                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "rgba(16, 185, 129, 0.1)", color: "var(--risk-low)", border: "1px solid rgba(16, 185, 129, 0.2)", padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 800, textTransform: "uppercase" }}><CheckCircle2 size={12} /> Success</span>
                                                        ) : (
                                                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "rgba(239, 68, 68, 0.1)", color: "var(--risk-high)", border: "1px solid rgba(239, 68, 68, 0.2)", padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 800, textTransform: "uppercase" }}><XCircle size={12} /> Failed</span>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: "16px 24px" }}>
                                                        {r.score !== undefined ? (
                                                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                                                <div style={{ width: 60, height: 6, background: "var(--border-inner)", borderRadius: 99, overflow: "hidden" }}>
                                                                    <div style={{ width: `${r.score}%`, height: "100%", background: getRiskColor(r.score), borderRadius: 99, boxShadow: `0 0 8px ${getRiskColor(r.score)}` }} />
                                                                </div>
                                                                <span style={{ fontWeight: 800, fontFamily: "var(--font-mono)", color: getRiskColor(r.score), fontSize: 14 }}>
                                                                    {r.score.toFixed(1)}
                                                                </span>
                                                            </div>
                                                        ) : (
                                                            <span style={{ color: "var(--text-muted)", fontSize: 14 }}>-</span>
                                                        )}
                                                    </td>
                                                    <td style={{ padding: "16px 24px" }}>
                                                        {r.classification ? (
                                                            <span style={{ fontWeight: 700, color: "var(--text-primary)", textTransform: "capitalize", fontSize: 14 }}>
                                                                {r.classification.replace(/_/g, ' ')}
                                                            </span>
                                                        ) : (
                                                            <span style={{ color: "var(--text-muted)", fontSize: 14 }}>-</span>
                                                        )}
                                                    </td>
                                                </tr>
                                            )) : (
                                                <tr><td colSpan="4" style={{ padding: "40px", textAlign: "center", color: "var(--text-muted)" }}>No results match the selected filter.</td></tr>
                                            )}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </>
                    )}
                    
                    {jobStatus?.status === "completed" && (
                        <div style={{ textAlign: "center", marginTop: 40 }}>
                            <button 
                                onClick={() => { setJobId(null); setJobStatus(null); setFile(null); setFilter("all"); }}
                                className="btn-ghost flex items-center gap-2 mx-auto"
                            >
                                ← New Bulk Scan
                            </button>
                        </div>
                    )}
                </div>
            )}
            
            <style>{`
                @keyframes shimmer {
                    0% { transform: skewX(-20deg) translateX(-150%); }
                    100% { transform: skewX(-20deg) translateX(250%); }
                }
            `}</style>
        </div>
    );
}
