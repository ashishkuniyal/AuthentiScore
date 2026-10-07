import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { User, Shield, Bell, Settings, CreditCard, Key, Users, Activity, CheckCircle2, AlertCircle } from "lucide-react";

export default function ProfilePage({ initialTab = "overview" }) {
    const { user, token, refreshUser } = useAuth();
    const [activeSection, setActiveSection] = useState(initialTab);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState(null);
    
    // User Profile Form State
    const [profileData, setProfileData] = useState({
        firstName: "", lastName: "", username: "", email: "", phone: "", jobTitle: "", company: "", bio: ""
    });

    // Preferences State
    const [prefs, setPrefs] = useState({
        appearance: "Dark", dashboard_view: "Overview", analytics_period: "30",
        default_platform: "Instagram", history_retention: "30", rows_per_page: "10"
    });

    // Notifications State
    const [notifs, setNotifs] = useState({
        scan_completed: true, high_risk: true, bulk_completed: true,
        ai_insights: true, security_alerts: true, product_updates: false
    });

    // Stats and Activity
    const [stats, setStats] = useState(null);
    const [activity, setActivity] = useState([]);
    const [apiKeys, setApiKeys] = useState([]);
    const [billing, setBilling] = useState(null);
    
    useEffect(() => {
        if (user) {
            setProfileData({
                firstName: user.firstName || "",
                lastName: user.lastName || "",
                username: user.username || "",
                email: user.email || "",
                phone: user.phone || "",
                jobTitle: user.jobTitle || "",
                company: user.company || "",
                bio: user.bio || ""
            });
            if (user.preferences) setPrefs(user.preferences);
            if (user.notifications) setNotifs(user.notifications);
        }
    }, [user]);

    useEffect(() => {
        if (activeSection === "activity") fetchActivity();
        if (activeSection === "api-keys") fetchApiKeys();
        if (activeSection === "billing") fetchBilling();
        if (activeSection === "overview") fetchStats();
    }, [activeSection]);

    const showMessage = (msg, type = "success") => {
        setMessage({ text: msg, type });
        setTimeout(() => setMessage(null), 3000);
    };

    const fetchStats = async () => {
        try {
            const res = await fetch("http://localhost:8000/users/stats", { headers: { "Authorization": `Bearer ${token}` } });
            if (res.ok) setStats(await res.json());
        } catch (e) {}
    };

    const fetchActivity = async () => {
        try {
            const res = await fetch("http://localhost:8000/users/activity", { headers: { "Authorization": `Bearer ${token}` } });
            if (res.ok) setActivity(await res.json());
        } catch (e) {}
    };

    const fetchApiKeys = async () => {
        try {
            const res = await fetch("http://localhost:8000/users/api-keys", { headers: { "Authorization": `Bearer ${token}` } });
            if (res.ok) setApiKeys(await res.json());
        } catch (e) {}
    };

    const fetchBilling = async () => {
        try {
            const res = await fetch("http://localhost:8000/users/billing", { headers: { "Authorization": `Bearer ${token}` } });
            if (res.ok) setBilling(await res.json());
        } catch (e) {}
    };

    const handleProfileSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await fetch("http://localhost:8000/users/profile", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify(profileData)
            });
            if (res.ok) {
                showMessage("Profile updated successfully");
                await refreshUser();
            } else {
                showMessage("Failed to update profile", "error");
            }
        } catch (err) {
            showMessage("An error occurred", "error");
        } finally {
            setLoading(false);
        }
    };

    const handlePrefsSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await fetch("http://localhost:8000/users/preferences", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify(prefs)
            });
            if (res.ok) {
                showMessage("Preferences saved");
                await refreshUser();
            }
        } catch (err) {} finally { setLoading(false); }
    };

    const handleNotifsSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await fetch("http://localhost:8000/users/notifications", {
                method: "PUT",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify(notifs)
            });
            if (res.ok) {
                showMessage("Notification settings saved");
                await refreshUser();
            }
        } catch (err) {} finally { setLoading(false); }
    };

    const createApiKey = async () => {
        const name = prompt("Enter a name for this API key:");
        if (!name) return;
        try {
            const res = await fetch("http://localhost:8000/users/api-keys", {
                method: "POST",
                headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            if (res.ok) {
                alert(`API Key created!\n\n${data.api_key}\n\nPlease copy it now. You won't be able to see it again.`);
                fetchApiKeys();
            }
        } catch (err) {}
    };

    const revokeApiKey = async (id) => {
        if (!confirm("Are you sure you want to revoke this API key?")) return;
        try {
            const res = await fetch(`http://localhost:8000/users/api-keys/${id}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) fetchApiKeys();
        } catch (err) {}
    };

    const sections = [
        { id: "overview", label: "Overview", icon: <User size={18} /> },
        { id: "profile", label: "Personal Information", icon: <User size={18} /> },
        { id: "security", label: "Security", icon: <Shield size={18} /> },
        { id: "notifications", label: "Notifications", icon: <Bell size={18} /> },
        { id: "preferences", label: "Preferences", icon: <Settings size={18} /> },
        { id: "billing", label: "Billing", icon: <CreditCard size={18} /> },
        { id: "api-keys", label: "API Keys", icon: <Key size={18} /> },
        { id: "team", label: "Team", icon: <Users size={18} /> },
        { id: "activity", label: "Activity", icon: <Activity size={18} /> },
    ];

    if (!user) return <div className="p-10 text-center">Loading...</div>;

    const calcProfileCompletion = () => {
        const fields = ['firstName', 'lastName', 'username', 'email', 'phone', 'jobTitle', 'company', 'bio'];
        const filled = fields.filter(f => profileData[f] && profileData[f].trim() !== "").length;
        return Math.round((filled / fields.length) * 100);
    };

    const pct = calcProfileCompletion();

    const handleAvatarChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setProfileData({ ...profileData, avatar: reader.result });
            };
            reader.readAsDataURL(file);
        }
    };

    return (
        <div style={{ padding: "40px 32px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
            
            <div style={{ marginBottom: 30 }}>
                <h1 style={{ fontFamily: "var(--font-head)", fontSize: 32, fontWeight: 900, color: "var(--text-primary)", marginBottom: 8 }}>Profile Settings</h1>
                <p style={{ color: "var(--text-secondary)" }}>Manage your personal information and AuthenticScore account.</p>
            </div>

            <div style={{ display: "flex", gap: 32, flexWrap: "wrap", alignItems: "flex-start" }}>
                
                {/* Left Sidebar Menu */}
                <div style={{ width: 260, flexShrink: 0 }} className="premium-glass p-3">
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {sections.map(s => (
                            <button
                                key={s.id}
                                onClick={() => setActiveSection(s.id)}
                                style={{
                                    display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
                                    borderRadius: 8, background: activeSection === s.id ? "var(--border-inner)" : "transparent",
                                    color: activeSection === s.id ? "var(--accent-light)" : "var(--text-secondary)",
                                    border: "none", cursor: "pointer", textAlign: "left", fontWeight: activeSection === s.id ? 600 : 500,
                                    transition: "all 0.2s"
                                }}
                                onMouseEnter={e => { if(activeSection !== s.id) e.currentTarget.style.background = "var(--bg-surface-secondary)" }}
                                onMouseLeave={e => { if(activeSection !== s.id) e.currentTarget.style.background = "transparent" }}
                            >
                                {s.icon} {s.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Right Content Panel */}
                <div style={{ flex: 1, minWidth: 0 }}>
                    {message && (
                        <div style={{ marginBottom: 20, padding: "12px 16px", borderRadius: 8, display: "flex", alignItems: "center", gap: 10, background: message.type === "error" ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)", border: `1px solid ${message.type === "error" ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)"}`, color: message.type === "error" ? "#ef4444" : "#10b981", fontWeight: 600 }}>
                            {message.type === "error" ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
                            {message.text}
                        </div>
                    )}

                    {activeSection === "overview" && (
                        <div className="animate-fade-in flex flex-col gap-6">
                            {/* Profile Card */}
                            <div className="premium-glass p-8 flex flex-col md:flex-row items-center md:items-start gap-8 relative overflow-hidden">
                                <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--accent)] opacity-5 blur-[80px] rounded-full pointer-events-none" />
                                
                                <div style={{ width: 100, height: 100, borderRadius: "50%", background: "var(--bg-surface)", border: "2px solid var(--border-inner)", overflow: "hidden", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                                    {user.avatar ? <img src={user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <User size={40} color="var(--text-muted)" />}
                                </div>
                                
                                <div style={{ flex: 1, textAlign: "center", md: {textAlign: "left"} }}>
                                    <h2 style={{ fontFamily: "var(--font-head)", fontSize: 28, fontWeight: 900, color: "var(--text-primary)", marginBottom: 4 }}>
                                        {user.firstName} {user.lastName}
                                    </h2>
                                    <div style={{ color: "var(--text-secondary)", fontSize: 15, marginBottom: 12 }}>{user.email}</div>
                                    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", justifyContent: "center", md: {justifyContent: "flex-start"} }}>
                                        <span style={{ padding: "4px 10px", background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)", borderRadius: 99, fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{user.role}</span>
                                        <span style={{ padding: "4px 10px", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)", borderRadius: 99, fontSize: 12, fontWeight: 700, color: "var(--risk-low)", display: "flex", alignItems: "center", gap: 4 }}><div style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--risk-low)" }}/> {user.accountStatus}</span>
                                    </div>
                                    <div style={{ display: "flex", gap: 24, marginTop: 24, fontSize: 13, color: "var(--text-muted)", borderTop: "1px solid var(--border-inner)", paddingTop: 16 }}>
                                        <div>Member since: <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{new Date(user.createdAt).toLocaleDateString()}</span></div>
                                        <div>Last active: <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>Today</span></div>
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div className="premium-glass p-6">
                                    <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Profile Completion</h3>
                                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 14 }}>
                                        <span style={{ color: "var(--text-secondary)" }}>Profile Complete</span>
                                        <span style={{ fontWeight: 700, color: "var(--accent-light)" }}>{pct}%</span>
                                    </div>
                                    <div className="progress-track" style={{ height: 8, background: "var(--bg-surface-secondary)", marginBottom: 16 }}>
                                        <div className="progress-fill" style={{ width: `${pct}%`, background: "var(--accent)", boxShadow: "0 0 10px var(--accent)" }} />
                                    </div>
                                    {pct < 100 && (
                                        <button onClick={() => setActiveSection("profile")} className="btn-ghost w-full" style={{ fontSize: 13 }}>Complete Profile →</button>
                                    )}
                                </div>
                                <div className="premium-glass p-6">
                                    <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16 }}>Account Statistics</h3>
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                                        <div>
                                            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Total Scans</div>
                                            <div style={{ fontSize: 24, fontWeight: 900, fontFamily: "var(--font-head)" }}>{stats?.totalScans ?? "-"}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Fake Detected</div>
                                            <div style={{ fontSize: 24, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--risk-high)" }}>{stats?.fakeProfiles ?? "-"}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Authentic</div>
                                            <div style={{ fontSize: 24, fontWeight: 900, fontFamily: "var(--font-head)", color: "var(--risk-low)" }}>{stats?.authenticProfiles ?? "-"}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Reports</div>
                                            <div style={{ fontSize: 24, fontWeight: 900, fontFamily: "var(--font-head)" }}>{stats?.reportsGenerated ?? "-"}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeSection === "profile" && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>Personal Information</h2>
                            <form onSubmit={handleProfileSubmit}>
                                <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 30 }}>
                                    <div style={{ width: 80, height: 80, borderRadius: "50%", background: "var(--bg-surface)", border: "2px solid var(--border-inner)", overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                                        {profileData.avatar || user?.avatar ? <img src={profileData.avatar || user.avatar} alt="Avatar" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <User size={32} color="var(--text-muted)" />}
                                    </div>
                                    <div>
                                        <label className="btn-ghost cursor-pointer" style={{ fontSize: 13, display: "inline-block" }}>
                                            Change Avatar
                                            <input type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
                                        </label>
                                        <div style={{ fontSize: 11, color: "var(--text-muted)", mt: 4 }}>JPG, GIF or PNG. Max size of 800K</div>
                                    </div>
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>First Name</label>
                                        <input required type="text" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.firstName} onChange={e => setProfileData({...profileData, firstName: e.target.value})} />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Last Name</label>
                                        <input required type="text" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.lastName} onChange={e => setProfileData({...profileData, lastName: e.target.value})} />
                                    </div>
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Email Address</label>
                                        <input required type="email" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.email} onChange={e => setProfileData({...profileData, email: e.target.value})} />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Username</label>
                                        <input required type="text" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.username} onChange={e => setProfileData({...profileData, username: e.target.value})} />
                                    </div>
                                </div>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 20 }}>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Phone Number</label>
                                        <input type="tel" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.phone} onChange={e => setProfileData({...profileData, phone: e.target.value})} />
                                    </div>
                                    <div>
                                        <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Job Title</label>
                                        <input type="text" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.jobTitle} onChange={e => setProfileData({...profileData, jobTitle: e.target.value})} />
                                    </div>
                                </div>
                                <div style={{ marginBottom: 20 }}>
                                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Company</label>
                                    <input type="text" className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.company} onChange={e => setProfileData({...profileData, company: e.target.value})} />
                                </div>
                                <div style={{ marginBottom: 30 }}>
                                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Bio</label>
                                    <textarea rows={4} className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none focus:border-[var(--accent)]" value={profileData.bio} onChange={e => setProfileData({...profileData, bio: e.target.value})} />
                                </div>
                                <div style={{ display: "flex", gap: 16 }}>
                                    <button type="submit" className="btn-primary flex-1" disabled={loading}>
                                        {loading ? "Saving..." : "Save Changes"}
                                    </button>
                                    <button type="button" className="btn-ghost flex-1">Cancel</button>
                                </div>
                            </form>
                        </div>
                    )}

                    {activeSection === "security" && (
                        <div className="premium-glass p-8 animate-fade-in flex flex-col gap-8">
                            <div>
                                <h2 style={{ fontSize: 18, fontWeight: 800, marginBottom: 16 }}>Password</h2>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 8 }}>
                                    <div>
                                        <div style={{ fontWeight: 600 }}>********</div>
                                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>Last changed 3 months ago</div>
                                    </div>
                                    <button className="btn-ghost" onClick={() => alert("Coming soon")}>Change Password</button>
                                </div>
                            </div>
                            <div>
                                <h2 style={{ fontSize: 18, fontWeight: 800, marginBottom: 16 }}>Two-Factor Authentication</h2>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 8 }}>
                                    <div>
                                        <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                                            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--text-muted)" }} /> Disabled
                                        </div>
                                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>Add an extra layer of security to your account.</div>
                                    </div>
                                    <button className="btn-ghost" onClick={() => alert("Coming soon")}>Enable 2FA</button>
                                </div>
                            </div>
                            <div>
                                <h2 style={{ fontSize: 18, fontWeight: 800, marginBottom: 16 }}>Login Sessions</h2>
                                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", background: "var(--bg-surface-secondary)", border: "1px solid var(--bg-surface-secondary)", borderRadius: 8 }}>
                                        <div>
                                            <div style={{ fontWeight: 600 }}>Windows • Chrome</div>
                                            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>Current session • Just now</div>
                                        </div>
                                        <span style={{ fontSize: 12, fontWeight: 700, color: "var(--risk-low)", padding: "4px 8px", background: "rgba(16,185,129,0.1)", borderRadius: 4 }}>Active</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeSection === "notifications" && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>Notification Preferences</h2>
                            <form onSubmit={handleNotifsSubmit}>
                                <div style={{ display: "flex", flexDirection: "column", gap: 20, marginBottom: 30 }}>
                                    {Object.entries({
                                        scan_completed: "Scan completed",
                                        high_risk: "High-risk profile detected",
                                        bulk_completed: "Bulk analysis completed",
                                        ai_insights: "AI insights available",
                                        security_alerts: "Security alerts",
                                        product_updates: "Product updates"
                                    }).map(([key, label]) => (
                                        <label key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
                                            <span style={{ fontSize: 14, fontWeight: 500 }}>{label}</span>
                                            <input type="checkbox" checked={notifs[key] || false} onChange={e => setNotifs({...notifs, [key]: e.target.checked})} style={{ width: 18, height: 18, accentColor: "var(--accent)" }} />
                                        </label>
                                    ))}
                                </div>
                                <button type="submit" className="btn-primary w-full" disabled={loading}>{loading ? "Saving..." : "Save Preferences"}</button>
                            </form>
                        </div>
                    )}

                    {activeSection === "preferences" && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>System Preferences</h2>
                            <form onSubmit={handlePrefsSubmit} className="flex flex-col gap-6">
                                <div>
                                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Appearance</label>
                                    <select className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none" value={prefs.appearance} onChange={e => setPrefs({...prefs, appearance: e.target.value})}>
                                        <option value="Dark" style={{ background: "var(--bg-card)" }}>Dark</option>
                                        <option value="Light" style={{ background: "var(--bg-card)" }}>Light</option>
                                        <option value="System" style={{ background: "var(--bg-card)" }}>System Default</option>
                                    </select>
                                </div>
                                <div>
                                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Default Dashboard View</label>
                                    <select className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none" value={prefs.dashboard_view} onChange={e => setPrefs({...prefs, dashboard_view: e.target.value})}>
                                        <option value="Overview" style={{ background: "var(--bg-card)" }}>Overview</option>
                                        <option value="Analytics" style={{ background: "var(--bg-card)" }}>Analytics</option>
                                        <option value="History" style={{ background: "var(--bg-card)" }}>History</option>
                                    </select>
                                </div>
                                <div>
                                    <label style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 8 }}>Rows per page (Tables)</label>
                                    <select className="form-input w-full bg-[var(--bg-surface-secondary)] border-[var(--border-inner)] rounded-lg px-4 py-2 text-[var(--text-primary)] outline-none" value={prefs.rows_per_page} onChange={e => setPrefs({...prefs, rows_per_page: e.target.value})}>
                                        <option value="10" style={{ background: "var(--bg-card)" }}>10</option>
                                        <option value="25" style={{ background: "var(--bg-card)" }}>25</option>
                                        <option value="50" style={{ background: "var(--bg-card)" }}>50</option>
                                    </select>
                                </div>
                                <button type="submit" className="btn-primary mt-4" disabled={loading}>{loading ? "Saving..." : "Save Changes"}</button>
                            </form>
                        </div>
                    )}

                    {activeSection === "api-keys" && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>
                                <h2 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>API Keys</h2>
                                <button className="btn-primary text-sm px-4 py-2" onClick={createApiKey}>Create New Key</button>
                            </div>
                            
                            {apiKeys.length === 0 ? (
                                <div className="text-center p-8 text-[var(--text-muted)]">No API keys generated yet.</div>
                            ) : (
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="border-b border-[var(--border-inner)] text-[var(--text-muted)] text-xs uppercase tracking-wider">
                                            <th className="pb-3">Name</th>
                                            <th className="pb-3">Key Hint</th>
                                            <th className="pb-3">Created</th>
                                            <th className="pb-3">Status</th>
                                            <th className="pb-3 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {apiKeys.map(k => (
                                            <tr key={k.id} className="border-b border-[var(--bg-surface-secondary)]">
                                                <td className="py-4 font-semibold">{k.name}</td>
                                                <td className="py-4 font-mono text-sm text-[var(--text-secondary)]">{k.key_hint}</td>
                                                <td className="py-4 text-sm text-[var(--text-secondary)]">{new Date(k.created_at).toLocaleDateString()}</td>
                                                <td className="py-4">
                                                    {k.status === "Active" ? 
                                                        <span className="bg-[rgba(16,185,129,0.1)] text-[#10b981] px-2 py-1 rounded text-xs font-bold">ACTIVE</span> : 
                                                        <span className="bg-[rgba(239,68,68,0.1)] text-[#ef4444] px-2 py-1 rounded text-xs font-bold">REVOKED</span>
                                                    }
                                                </td>
                                                <td className="py-4 text-right">
                                                    {k.status === "Active" && (
                                                        <button className="text-[#ef4444] text-sm font-semibold hover:underline" onClick={() => revokeApiKey(k.id)}>Revoke</button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    )}

                    {activeSection === "billing" && billing && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>Billing & Plan</h2>
                            
                            <div className="bg-[var(--bg-surface-secondary)] border border-[var(--bg-surface-secondary)] rounded-xl p-6 mb-8 flex justify-between items-center">
                                <div>
                                    <div className="text-[var(--text-muted)] text-sm font-bold uppercase tracking-wider mb-1">Current Plan</div>
                                    <div className="text-3xl font-black font-[var(--font-head)] text-[var(--accent)]">{billing.plan}</div>
                                </div>
                                <div className="text-right">
                                    <div className="text-2xl font-bold">{billing.price}</div>
                                </div>
                            </div>

                            <h3 className="text-lg font-bold mb-4">Current Usage</h3>
                            <div className="flex flex-col gap-6 mb-8">
                                <div>
                                    <div className="flex justify-between mb-2 text-sm">
                                        <span className="font-semibold text-[var(--text-secondary)]">Scans</span>
                                        <span className="font-bold">{billing.usage.scans.used} / {billing.usage.scans.limit}</span>
                                    </div>
                                    <div className="h-2 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                        <div className="h-full bg-[var(--accent)]" style={{ width: `${(billing.usage.scans.used / billing.usage.scans.limit) * 100}%` }} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between mb-2 text-sm">
                                        <span className="font-semibold text-[var(--text-secondary)]">Bulk Profiles</span>
                                        <span className="font-bold">{billing.usage.bulk.used} / {billing.usage.bulk.limit}</span>
                                    </div>
                                    <div className="h-2 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden">
                                        <div className="h-full bg-[var(--violet)]" style={{ width: `${(billing.usage.bulk.used / billing.usage.bulk.limit) * 100}%` }} />
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-4">
                                <button className="btn-primary" onClick={() => alert("Billing portal coming soon")}>Upgrade Plan</button>
                                <button className="btn-ghost" onClick={() => alert("Billing portal coming soon")}>Manage Subscription</button>
                            </div>
                        </div>
                    )}

                    {activeSection === "activity" && (
                        <div className="premium-glass p-8 animate-fade-in">
                            <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 24, borderBottom: "1px solid var(--border-inner)", paddingBottom: 16 }}>Account Activity</h2>
                            {activity.length === 0 ? (
                                <div className="text-center p-8 text-[var(--text-muted)]">No recent activity.</div>
                            ) : (
                                <div className="flex flex-col gap-4">
                                    {activity.map(log => (
                                        <div key={log.id} className="flex items-start gap-4 p-4 border-b border-[var(--bg-surface-secondary)] last:border-0">
                                            <div className="w-8 h-8 rounded-full bg-[var(--bg-surface-secondary)] flex items-center justify-center text-[var(--text-secondary)] mt-1">
                                                <Activity size={14} />
                                            </div>
                                            <div>
                                                <div className="font-semibold text-[var(--text-primary)]">{log.action}</div>
                                                {log.details && <div className="text-sm text-[var(--text-secondary)] mt-1">{log.details}</div>}
                                                <div className="text-xs text-[var(--text-muted)] mt-2 font-mono">{new Date(log.timestamp).toLocaleString()}</div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {activeSection === "team" && (
                        <div className="premium-glass p-8 animate-fade-in text-center py-20">
                            <Users size={48} className="mx-auto text-[var(--text-muted)] mb-4" />
                            <h2 className="text-xl font-bold mb-2">Team & Organization</h2>
                            <p className="text-[var(--text-secondary)] mb-6 max-w-md mx-auto">Invite members, assign roles, and collaborate on threat intelligence across your organization.</p>
                            <button className="btn-primary" onClick={() => alert("Team management requires Enterprise plan")}>Upgrade to Enterprise</button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
