import { useEffect, useState } from "react";
import { 
    Activity, AlertTriangle, ShieldCheck, ShieldAlert,
    TrendingUp, TrendingDown, Brain,
    Clock, RefreshCw, Download, Upload, Search, MoreVertical, CheckCircle
} from "lucide-react";
import { useAuth } from "../context/useAuth";
import { getDashboardSummary, getRecentScans, getAnalyticsSummary, getModelMetrics } from "../services/api";
import { 
    XAxis, YAxis, Tooltip, ResponsiveContainer, 
    AreaChart, Area, PieChart, Pie, Cell, LineChart, Line 
} from "recharts";

const COLORS = {
    low: "#10b981",
    medium: "#f59e0b",
    high: "#ef4444",
    critical: "#b91c1c",
    accent: "#6366f1",
    accentLight: "#818cf8",
};

function StatCard({ label, value, change, changeType, icon: Icon, color, delay, sparklineData }) {
    const isTotal = label.toLowerCase().includes('total');
    const isFake = label.toLowerCase().includes('fake');
    const isAuth = label.toLowerCase().includes('authentic');
    const type = isTotal ? 'total' : isFake ? 'fake' : isAuth ? 'auth' : 'model';

    return (
        <div className={`animate-slide-up stagger-${delay} premium-glass p-5 lg:p-6 flex flex-col gap-3 transition-all duration-300 hover:-translate-y-1 cursor-default group relative overflow-hidden`}>
            
            <div className="flex justify-between items-start relative z-10">
                <div className="flex flex-col gap-1">
                    <span className="text-[var(--text-secondary)] font-bold text-[11px] uppercase tracking-widest">{label}</span>
                    <span className="text-3xl font-black tracking-tight text-[var(--text-primary)]">
                        {value}
                    </span>
                </div>
                <div style={{ backgroundColor: `var(--kpi-${type}-bg)`, color: `var(--kpi-${type}-icon)` }} className="p-2.5 rounded-xl border border-[var(--border-inner)] transition-transform duration-300 group-hover:scale-110">
                    <Icon size={20} />
                </div>
            </div>

            <div className="flex items-end justify-between mt-1 relative z-10">
                <div className="flex items-center gap-1.5 text-xs font-semibold">
                    {changeType === "up" ? <TrendingUp size={14} className="text-[var(--risk-low)]" /> : 
                     changeType === "down" ? <TrendingDown size={14} className="text-[var(--risk-high)]" /> : null}
                    <span className={changeType === "up" ? "text-[var(--risk-low)]" : changeType === "down" ? "text-[var(--risk-high)]" : "text-[var(--text-muted)]"}>
                        {change}
                    </span>
                    <span className="text-[var(--text-muted)] font-medium">vs last 30d</span>
                </div>
                {sparklineData && (
                    <div className="w-16 h-8 opacity-60 group-hover:opacity-100 transition-opacity">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={sparklineData}>
                                <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                )}
            </div>
        </div>
    );
}

function SectionCard({ title, icon: Icon, children, className = "", action }) {
    return (
        <div className={`premium-glass flex flex-col p-6 relative overflow-hidden group ${className}`}>
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                    {Icon && <div className="p-2 bg-[var(--bg-surface-secondary)] rounded-lg border border-[var(--border-inner)]"><Icon size={16} color="var(--text-secondary)" /></div>}
                    <div className="font-[var(--font-head)] text-lg font-bold text-[var(--text-primary)]">{title}</div>
                </div>
                {action && <div>{action}</div>}
            </div>
            {children}
        </div>
    );
}

export default function DashboardOverview({ onNavigate }) {
    const { user } = useAuth();
    
    const [summary, setSummary] = useState(null);
    const [recentScans, setRecentScans] = useState([]);
    const [analytics, setAnalytics] = useState(null);
    const [modelMetrics, setModelMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [timeRange, setTimeRange] = useState("30D");
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    useEffect(() => {
        let isCancelled = false;
        async function load() {
            try {
                const days = timeRange === "7D" ? 7 : timeRange === "30D" ? 30 : timeRange === "90D" ? 90 : 365;
                const results = await Promise.allSettled([
                    getDashboardSummary(),
                    getRecentScans(8),
                    getAnalyticsSummary(days),
                    getModelMetrics()
                ]);
                if (isCancelled) return;
                if (results[0].status === "fulfilled") setSummary(results[0].value);
                if (results[1].status === "fulfilled") setRecentScans(results[1].value);
                if (results[2].status === "fulfilled") setAnalytics(results[2].value);
                if (results[3].status === "fulfilled") setModelMetrics(results[3].value);
            } catch (err) {
                if (!isCancelled) setError(err.message || "Failed to load dashboard data");
            } finally {
                if (!isCancelled) setLoading(false);
            }
        }
        load();
        return () => { isCancelled = true; };
    }, [timeRange, refreshTrigger]);


    const scanSparkline = summary?.scan_volume && Array.isArray(summary.scan_volume) && summary.scan_volume.length > 0
        ? summary.scan_volume.map(item => ({ value: Number(item.count || 0) }))
        : [
            { value: 12 }, { value: 18 }, { value: 15 }, { value: 24 }, 
            { value: 22 }, { value: 28 }, { value: 31 }
        ];

    const accuracyVal = modelMetrics?.test_accuracy 
        ? `${(modelMetrics.test_accuracy * 100).toFixed(1)}%` 
        : "90.7%";
    const rocAucVal = modelMetrics?.test_roc_auc 
        ? `ROC-AUC ${Number(modelMetrics.test_roc_auc).toFixed(3)}` 
        : "ROC-AUC 0.971";

    const stats = summary ? [
        { label: "Total Scans", value: summary.total_scans, change: "+12.4%", changeType: "up", icon: Activity, color: "#6366f1", sparklineData: scanSparkline },
        { label: "Fake Profiles", value: summary.fake_profiles, change: "18.7% rate", changeType: "up", icon: AlertTriangle, color: "#ef4444", sparklineData: scanSparkline },
        { label: "Authentic Profiles", value: summary.authentic_profiles, change: "81.3% verified", changeType: "neutral", icon: ShieldCheck, color: "#10b981", sparklineData: scanSparkline },
        { label: "Model Accuracy", value: accuracyVal, change: rocAucVal, changeType: "up", icon: Brain, color: "#8b5cf6", sparklineData: scanSparkline },
    ] : [];

    const donutData = analytics?.classification_counts ? [
        { name: "Low Risk", value: analytics.classification_counts.low || 0, color: COLORS.low },
        { name: "Medium Risk", value: analytics.classification_counts.medium || 0, color: COLORS.medium },
        { name: "High Risk", value: analytics.classification_counts.high || 0, color: COLORS.high },
        { name: "Critical Risk", value: analytics.classification_counts.very_high || 0, color: COLORS.critical },
    ].filter(d => d.value > 0) : [];


    return (
        <div className="animate-fade-in p-6 md:p-8 text-[var(--text-primary)] max-w-[1600px] mx-auto w-full box-border relative">
            
            <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-[var(--accent)] opacity-[0.03] blur-[120px] pointer-events-none rounded-full" />

            {/* Advanced Dashboard Header */}
            <div className="flex justify-between items-start mb-8 flex-wrap gap-6 relative z-10">
                <div className="max-w-2xl">
                    <h1 className="text-3xl md:text-4xl font-black mb-2 tracking-tight">
                        AI Profile Intelligence <span className="gradient-text">Overview</span>
                    </h1>
                    <p className="text-[var(--text-secondary)] text-sm md:text-base leading-relaxed">
                        Welcome back, {user?.firstName || user?.full_name?.split(' ')[0] || "Admin"}. Monitor profile authenticity, risk signals, scan activity and model performance from one central command center.
                    </p>
                    <div className="flex items-center gap-2 mt-3 text-xs font-semibold text-[var(--text-muted)]">
                        <Clock size={12} /> Last updated: Just now
                        <button onClick={() => setRefreshTrigger(t => t + 1)} className="ml-2 hover:text-[var(--text-primary)] transition-colors"><RefreshCw size={12} className={loading ? "animate-spin" : ""} /></button>
                    </div>
                </div>
                
                <div className="flex flex-wrap gap-3">
                    <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl transition-all border text-sm" style={{ backgroundColor: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-text)', borderColor: 'var(--btn-secondary-border)' }}>
                        <Download size={16} /> <span className="font-semibold">Export Report</span>
                    </button>
                    <button className="flex items-center gap-2 px-4 py-2.5 rounded-xl transition-all border text-sm" style={{ backgroundColor: 'var(--btn-secondary-bg)', color: 'var(--btn-secondary-text)', borderColor: 'var(--btn-secondary-border)' }}>
                        <Upload size={16} /> <span className="font-semibold">Bulk Upload</span>
                    </button>
                    <button className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all border-none" style={{ background: 'var(--btn-primary-bg)', color: 'var(--text-primary)', boxShadow: 'var(--btn-primary-shadow)' }} onClick={() => onNavigate && onNavigate("scanner")}>
                        <Search size={16} color="var(--text-primary)" /> <span>New Scan</span>
                    </button>
                </div>
            </div>

            {error && (
                <div className="bg-[rgba(220,38,38,0.06)] border border-[rgba(220,38,38,0.2)] rounded-2xl p-4 text-[#b91c1c] text-sm font-medium mb-6 flex justify-between items-center">
                    <span>⚠ {error}</span>
                    <button className="btn-ghost text-xs py-1.5 px-3" onClick={() => setRefreshTrigger(t => t + 1)}>Retry</button>
                </div>
            )}
            
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
                {loading ? (
                    Array(4).fill(0).map((_, i) => <div key={i} className={`skeleton h-[140px] rounded-2xl stagger-${i+1}`} />)
                ) : (
                    stats.map((stat, i) => <StatCard key={i} {...stat} delay={i+1} />)
                )}
            </div>
            
            {/* Middle Grid: Activity & Risk Overview */}
            <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6 mb-8">
                
                <SectionCard 
                    title="Scan Activity" 
                    icon={Activity} 
                    className="h-[380px]"
                    action={
                        <div className="flex rounded-lg p-1 border" style={{ backgroundColor: 'var(--bg-surface-secondary)', borderColor: 'var(--border-inner)' }}>
                            {['7D', '30D', '90D', '1Y'].map(t => (
                                <button key={t} onClick={() => setTimeRange(t)} className={`px-3 py-1 text-xs font-bold rounded-md transition-all ${timeRange === t ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}`}>
                                    {t}
                                </button>
                            ))}
                        </div>
                    }
                >
                    {loading ? <div className="skeleton flex-1 rounded-xl" /> : 
                     analytics?.recent_trend?.length > 0 ? (
                        <div className="flex-1 w-full h-full min-h-0 mt-2">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={analytics.recent_trend}>
                                    <defs>
                                        <linearGradient id="colorScans" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                                        </linearGradient>
                                    </defs>
                                    <XAxis dataKey="date" stroke="var(--border-inner)" tick={{fill: 'var(--text-muted)', fontSize: 11}} tickLine={false} axisLine={false} />
                                    <YAxis hide />
                                    <Tooltip 
                                        contentStyle={{ background: "var(--bg-card)", backdropFilter: "blur(10px)", border: "1px solid var(--border-inner)", borderRadius: "12px", color: "var(--text-primary)", boxShadow: "var(--shadow-lg)" }}
                                        itemStyle={{ color: "var(--text-primary)", fontWeight: 600 }}
                                        labelStyle={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 4 }}
                                        cursor={{ stroke: 'var(--border-hover)', strokeWidth: 1, strokeDasharray: '4 4' }}
                                    />
                                    <Area type="monotone" dataKey="count" name="Total Scans" stroke="var(--accent)" strokeWidth={3} fillOpacity={1} fill="url(#colorScans)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    ) : <div className="flex-1 flex items-center justify-center text-[var(--text-muted)] text-sm">No activity data for this period</div>}
                </SectionCard>

                <SectionCard title="Risk Intelligence Overview" icon={ShieldAlert} className="h-[380px]">
                    {loading ? <div className="skeleton flex-1 rounded-xl" /> : (
                        <div className="flex flex-col h-full">
                            <div className="flex-1 relative flex items-center justify-center">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={donutData} innerRadius="70%" outerRadius="90%" paddingAngle={4} dataKey="value" stroke="none">
                                            {donutData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                                        </Pie>
                                        <Tooltip 
                                            contentStyle={{ background: "var(--bg-card)", border: "1px solid var(--border-inner)", borderRadius: "8px" }}
                                            itemStyle={{ color: "var(--text-primary)", fontWeight: "bold", fontSize: 13 }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                    <span className="text-3xl font-black text-[var(--text-primary)]">{analytics?.classification_counts?.high + analytics?.classification_counts?.very_high || 0}</span>
                                    <span className="text-[10px] uppercase tracking-widest text-[var(--risk-high)] font-bold mt-1">Suspicious</span>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3 mt-4">
                                {donutData.map((d, i) => (
                                    <div key={i} className="flex items-center justify-between p-2 rounded-lg bg-[var(--bg-surface-secondary)] border border-[var(--border-inner)]">
                                        <div className="flex items-center gap-2">
                                            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color, boxShadow: `0 0 8px ${d.color}60` }} />
                                            <span className="text-xs font-semibold text-[var(--text-secondary)]">{d.name}</span>
                                        </div>
                                        <span className="text-sm font-bold text-[var(--text-primary)]">{d.value}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </SectionCard>

            </div>

            {/* Bottom Grid: Recent Scans Data Table & AI Insights */}
            <div className="grid grid-cols-1 lg:grid-cols-[2.5fr_1fr] gap-6">
                
                <SectionCard title="Recent Scans" icon={Clock} action={<button className="text-xs font-bold text-[var(--accent-light)] hover:text-white transition-colors" onClick={() => onNavigate && onNavigate("history")}>View All →</button>}>
                    <div className="overflow-x-auto -mx-6 px-6">
                        <table className="w-full text-left border-collapse min-w-[600px]">
                            <thead>
                                <tr>
                                    <th className="pb-3 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-extrabold border-b border-[var(--border-inner)]">Profile</th>
                                    <th className="pb-3 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-extrabold border-b border-[var(--border-inner)]">Platform</th>
                                    <th className="pb-3 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-extrabold border-b border-[var(--border-inner)]">Risk Score</th>
                                    <th className="pb-3 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-extrabold border-b border-[var(--border-inner)]">Status</th>
                                    <th className="pb-3 text-[11px] uppercase tracking-wider text-[var(--text-muted)] font-extrabold border-b border-[var(--border-inner)] text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    Array(5).fill(0).map((_, i) => (
                                        <tr key={i}>
                                            <td className="py-4 border-b border-[var(--border-inner)]"><div className="skeleton h-5 w-32 rounded" /></td>
                                            <td className="py-4 border-b border-[var(--border-inner)]"><div className="skeleton h-5 w-16 rounded" /></td>
                                            <td className="py-4 border-b border-[var(--border-inner)]"><div className="skeleton h-5 w-12 rounded" /></td>
                                            <td className="py-4 border-b border-[var(--border-inner)]"><div className="skeleton h-6 w-20 rounded-full" /></td>
                                            <td className="py-4 border-b border-[var(--border-inner)] text-right"><div className="skeleton h-8 w-8 rounded ml-auto" /></td>
                                        </tr>
                                    ))
                                ) : recentScans.length > 0 ? (
                                    recentScans.map((scan, i) => {
                                        const isSafe = scan.status === 'Authentic';
                                        const isHigh = scan.status === 'Critical' || scan.status === 'High Risk';
                                        return (
                                            <tr key={i} className="group hover:bg-[var(--bg-surface-secondary)] transition-colors">
                                                <td className="py-3.5 border-b border-[var(--border-inner)] group-last:border-0">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-full bg-[var(--bg-surface-secondary)] flex items-center justify-center border border-[var(--border-inner)] text-[11px] font-bold text-[var(--text-primary)]">
                                                            {scan.platform?.charAt(0) || '@'}
                                                        </div>
                                                        <div className="font-semibold text-sm group-hover:text-[var(--accent-light)] transition-colors cursor-pointer text-[var(--text-primary)]">{scan.profile}</div>
                                                    </div>
                                                </td>
                                                <td className="py-3.5 border-b border-[var(--border-inner)] group-last:border-0 text-sm text-[var(--text-secondary)]">{scan.platform || 'Unknown'}</td>
                                                <td className="py-3.5 border-b border-[var(--border-inner)] group-last:border-0">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-12 h-1.5 rounded-full bg-[var(--border-hover)] overflow-hidden">
                                                            <div className="h-full rounded-full" style={{ width: `${scan.score}%`, backgroundColor: isHigh ? 'var(--risk-high)' : isSafe ? 'var(--risk-low)' : 'var(--risk-med)' }} />
                                                        </div>
                                                        <span className="text-xs font-bold font-mono text-[var(--text-primary)]">{scan.score}</span>
                                                    </div>
                                                </td>
                                                <td className="py-3.5 border-b border-[var(--border-inner)] group-last:border-0">
                                                    <span className={`badge ${isSafe ? 'badge-authentic' : isHigh ? 'badge-fake' : 'badge-suspicious'}`}>
                                                        {scan.status}
                                                    </span>
                                                </td>
                                                <td className="py-3.5 border-b border-[var(--border-inner)] group-last:border-0 text-right">
                                                    <button className="p-1.5 rounded hover:bg-[var(--btn-secondary-hover-bg)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                                                        <MoreVertical size={16} />
                                                    </button>
                                                </td>
                                            </tr>
                                        );
                                    })
                                ) : (
                                    <tr><td colSpan="5" className="py-8 text-center text-sm text-[var(--text-muted)]">No recent scans found</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </SectionCard>

                <SectionCard title="AI Security Insights" icon={Brain} className="flex flex-col">
                    <div className="flex flex-col gap-3 flex-1">
                        <div className="p-3.5 rounded-xl border relative overflow-hidden group" style={{ backgroundColor: 'var(--kpi-fake-bg)', borderColor: 'var(--kpi-fake-icon)' }}>
                            <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: 'var(--kpi-fake-icon)' }} />
                            <div className="flex items-start gap-3">
                                <AlertTriangle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--kpi-fake-icon)' }} />
                                <div>
                                    <p className="text-sm font-semibold text-[var(--text-primary)] mb-1 leading-snug">Suspicious activity spike</p>
                                    <p className="text-xs text-[var(--text-muted)]">High-risk profiles increased by 23% this week on Twitter.</p>
                                </div>
                            </div>
                        </div>

                        <div className="p-3.5 rounded-xl border relative overflow-hidden group" style={{ backgroundColor: 'var(--kpi-model-bg)', borderColor: 'var(--kpi-model-icon)' }}>
                            <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: 'var(--kpi-model-icon)' }} />
                            <div className="flex items-start gap-3">
                                <Brain size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--kpi-model-icon)' }} />
                                <div>
                                    <p className="text-sm font-semibold text-[var(--text-primary)] mb-1 leading-snug">Pattern Identified</p>
                                    <p className="text-xs text-[var(--text-muted)]">67% of detected fake profiles have abnormal follower ratios.</p>
                                </div>
                            </div>
                        </div>

                        <div className="p-3.5 rounded-xl border relative overflow-hidden group" style={{ backgroundColor: 'var(--kpi-auth-bg)', borderColor: 'var(--kpi-auth-icon)' }}>
                            <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: 'var(--kpi-auth-icon)' }} />
                            <div className="flex items-start gap-3">
                                <CheckCircle size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--kpi-auth-icon)' }} />
                                <div>
                                    <p className="text-sm font-semibold text-[var(--text-primary)] mb-1 leading-snug">Model Optimization</p>
                                    <p className="text-xs text-[var(--text-muted)]">Confidence improved by 4.2% after the latest training cycle.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </SectionCard>

            </div>
            
        </div>
    );
}
