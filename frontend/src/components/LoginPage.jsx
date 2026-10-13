import { useState } from "react";
import { useAuth } from "../context/useAuth";
import { Hexagon, Mail, Lock } from "lucide-react";

export default function LoginPage() {
    const { login, googleLogin } = useAuth();
    const [username, setUsername] = useState("admin@authentiscore.local");
    const [password, setPassword] = useState("admin");
    const [rememberMe, setRememberMe] = useState(true);
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(username, password, rememberMe);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleGoogleAuth = async () => {
        setError("");
        setLoading(true);
        try {
            await googleLogin();
            if (rememberMe) {
                localStorage.setItem("remember_me", "true");
            }
        } catch (err) {
            setError(err.message || "Google Sign-In failed.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-app)" }}>
            {/* Left Side: Abstract Graphic */}
            <div style={{ flex: 1, position: "relative", overflow: "hidden", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 60, borderRight: "1px solid var(--border)", background: "var(--bg-surface)" }} className="hidden lg:flex">
                <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: "150%", height: "150%", background: "radial-gradient(circle at center, rgba(109,74,255,0.08) 0%, rgba(0,0,0,0) 50%)", pointerEvents: "none" }} />
                
                <div style={{ position: "relative", zIndex: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--text-primary)", marginBottom: 20 }}>
                        <div style={{ width: 40, height: 40, borderRadius: 10, background: "linear-gradient(135deg, #6D4AFF 0%, #00ffff 100%)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}>
                            <Hexagon size={24} strokeWidth={2.5} />
                        </div>
                        <span style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.5px", fontFamily: "var(--font-head)" }}>AuthentiScore</span>
                    </div>
                </div>

                <div style={{ position: "relative", zIndex: 10 }}>
                    <h1 style={{ fontSize: 48, fontWeight: 800, lineHeight: 1.1, letterSpacing: "-1px", color: "var(--text-primary)", marginBottom: 24 }}>
                        Enterprise-Grade<br/>
                        <span style={{ background: "linear-gradient(to right, #6D4AFF, #00ffff)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                            Threat Intelligence.
                        </span>
                    </h1>
                    <p style={{ fontSize: 18, color: "var(--text-secondary)", maxWidth: 460, lineHeight: 1.6 }}>
                        Detect bot rings, analyze deepfakes, and secure your platform with the industry's most advanced profile analysis engine.
                    </p>
                </div>
            </div>

            {/* Right Side: Login Form */}
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 20px" }}>
                <div style={{ width: "100%", maxWidth: 400 }} className="animate-fade-in">
                    
                    <div style={{ marginBottom: 40, textAlign: "center" }} className="lg:hidden">
                        <div style={{ width: 48, height: 48, borderRadius: 12, background: "linear-gradient(135deg, #6D4AFF 0%, #00ffff 100%)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px", color: "var(--text-primary)" }}>
                            <Hexagon size={28} strokeWidth={2.5} />
                        </div>
                        <h2 style={{ fontSize: 24, fontWeight: 800, color: "var(--text-primary)" }}>AuthentiScore</h2>
                    </div>

                    <h2 style={{ fontSize: 28, fontWeight: 800, color: "var(--text-primary)", marginBottom: 8, letterSpacing: "-0.5px" }}>Welcome back</h2>
                    <p style={{ color: "var(--text-secondary)", fontSize: 15, marginBottom: 32 }}>Sign in to access your dashboard</p>

                    {/* SSO Buttons */}
                    <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
                        <button type="button" onClick={handleGoogleAuth} style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: "12px", background: "var(--btn-secondary-bg)", border: "1px solid var(--btn-secondary-border)", borderRadius: 12, color: "var(--text-primary)", fontSize: 14, fontWeight: 600, cursor: "pointer", transition: "all 0.2s" }} onMouseEnter={e => e.currentTarget.style.background="var(--btn-secondary-hover-bg)"} onMouseLeave={e => e.currentTarget.style.background="var(--btn-secondary-bg)"}>
                            <svg width="18" height="18" viewBox="0 0 24 24"><path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                            Google
                        </button>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24 }}>
                        <div style={{ flex: 1, height: 1, background: "var(--border-inner)" }} />
                        <span style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>or continue with</span>
                        <div style={{ flex: 1, height: 1, background: "var(--border-inner)" }} />
                    </div>

                    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                        <div>
                            <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>Work Email</label>
                            <div style={{ position: "relative" }}>
                                <Mail size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
                                <input
                                    type="text"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="input-field"
                                    style={{ paddingLeft: 40 }}
                                    disabled={loading}
                                />
                            </div>
                        </div>
                        <div>
                            <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                                Password
                                <a href="#" onClick={e=>e.preventDefault()} style={{ color: "var(--accent)", textDecoration: "none" }}>Forgot?</a>
                            </label>
                            <div style={{ position: "relative" }}>
                                <Lock size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="input-field"
                                    style={{ paddingLeft: 40 }}
                                    disabled={loading}
                                />
                            </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <input 
                                type="checkbox" 
                                id="rememberMe"
                                checked={rememberMe}
                                onChange={(e) => setRememberMe(e.target.checked)}
                                style={{ accentColor: "var(--accent)", cursor: "pointer", width: 16, height: 16 }}
                            />
                            <label htmlFor="rememberMe" style={{ fontSize: 14, color: "var(--text-secondary)", cursor: "pointer" }}>Remember me for 30 days</label>
                        </div>
                        
                        {error && (
                            <div style={{ padding: "12px", background: "var(--kpi-fake-bg)", border: "1px solid var(--kpi-fake-icon)", borderRadius: 10, fontSize: 13, color: "var(--kpi-fake-icon)", fontWeight: 500, display: "flex", alignItems: "center", gap: 8 }}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                                {error}
                            </div>
                        )}

                        <button type="submit" className="btn-primary" style={{ marginTop: 8, height: 48, fontSize: 15, width: "100%" }} disabled={loading}>
                            {loading ? "Signing in..." : "Sign In"}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
