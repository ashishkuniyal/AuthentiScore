import { useState } from "react";
import { sendEmailVerification } from "firebase/auth";
import { auth } from "./config/firebase";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import DashboardOverview from "./components/DashboardOverview";
import ScannerPage from "./components/ScannerPage";
import BulkScannerPage from "./components/BulkScannerPage";
import HistoryPage from "./components/HistoryPage";
import AnalyticsPage from "./components/AnalyticsPage";
import InfluencerAuditPage from "./components/InfluencerAuditPage";
import LoginPage from "./components/LoginPage";
import ProfilePage from "./components/ProfilePage";
import ToastContainer from "./components/Toast";
import { useAuth } from "./context/useAuth";
import { NotificationsProvider } from "./context/NotificationsContext";
import { useNotifications } from "./context/useNotifications";
import "./App.css";

function AppMain() {
    const [activeTab, setActiveTab] = useState("dashboard");
    const [globalSearchQuery, setGlobalSearchQuery] = useState("");
    const { notifications } = useNotifications();

    const handleGlobalSearch = (query) => {
        setGlobalSearchQuery(query);
        setActiveTab("scanner");
    };

    return (
        <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-app)", position: "relative", overflow: "hidden" }}>
            {/* Ambient Radial Glows */}
            <div style={{ position: "fixed", top: -300, left: -100, width: 800, height: 800, background: "radial-gradient(circle, rgba(0,112,243,0.08) 0%, rgba(0,0,0,0) 70%)", filter: "blur(80px)", borderRadius: "50%", pointerEvents: "none", zIndex: 0 }} />
            <div style={{ position: "fixed", bottom: -200, right: -100, width: 600, height: 600, background: "radial-gradient(circle, rgba(0,255,255,0.05) 0%, rgba(0,0,0,0) 70%)", filter: "blur(80px)", borderRadius: "50%", pointerEvents: "none", zIndex: 0 }} />
            
            <div style={{ zIndex: 10, display: "flex", width: "100%", height: "100%" }}>
                <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
                <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100vh", overflow: "auto" }}>
                    <Header activeTab={activeTab} notifications={notifications} onSearch={handleGlobalSearch} onNavigate={setActiveTab} />
                    <main style={{ flex: 1, position: "relative", overflowX: "hidden" }}>
                        {activeTab === "dashboard" && <DashboardOverview onNavigate={setActiveTab} />}
                        {activeTab === "scanner"   && <ScannerPage notifications={notifications} initialSearchQuery={globalSearchQuery} onClearSearch={() => setGlobalSearchQuery("")} />}
                        {activeTab === "bulk"      && <BulkScannerPage />}
                        {activeTab === "audit"     && <InfluencerAuditPage />}
                        {activeTab === "history"   && <HistoryPage />}
                        {activeTab === "analytics" && <AnalyticsPage />}
                        {activeTab.startsWith("profile") && <ProfilePage initialTab={activeTab.split(":")[1] || "overview"} />}
                        {["reports", "ai-insights", "risk-intel", "model-perf", "settings", "help"].includes(activeTab) && (
                            <div className="animate-fade-in p-6 md:p-10 flex flex-col items-center justify-center h-full text-center">
                                <div className="premium-glass p-10 max-w-md w-full flex flex-col items-center">
                                    <div className="w-16 h-16 rounded-2xl bg-[var(--accent)] bg-opacity-10 flex items-center justify-center mb-6 shadow-[0_0_20px_rgba(99,102,241,0.2)]">
                                        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
                                    </div>
                                    <h2 className="text-2xl font-bold mb-2">Module Coming Soon</h2>
                                    <p className="text-[var(--text-secondary)] mb-8">
                                        The <strong>{activeTab.replace('-', ' ')}</strong> module is currently in development and will be available in the next major update.
                                    </p>
                                    <button className="btn-primary w-full" onClick={() => setActiveTab("dashboard")}>
                                        Return to Dashboard
                                    </button>
                                </div>
                            </div>
                        )}
                    </main>
                </div>
            </div>
            <ToastContainer />
        </div>
    );
}

export default function App() {
    const { user, loading, authError, retryAuth, logout } = useAuth();
    const [sendingVerification, setSendingVerification] = useState(false);
    const [verificationSent, setVerificationSent] = useState(false);
    const [verifyError, setVerifyError] = useState(null);

    const handleResendVerification = async () => {
        if (!auth.currentUser) return;
        setSendingVerification(true);
        setVerifyError(null);
        try {
            await sendEmailVerification(auth.currentUser);
            setVerificationSent(true);
        } catch (e) {
            setVerifyError(e.message || "Failed to send verification email");
        } finally {
            setSendingVerification(false);
        }
    };

    if (loading) {
        return (
            <div style={{ height: "100vh", background: "var(--bg-app)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>
                Loading AuthentiScore...
            </div>
        );
    }

    if (authError) {
        const isVerificationError = authError.toLowerCase().includes("verified");
        return (
            <div className="h-screen w-screen flex items-center justify-center bg-[var(--bg-app)] p-6">
                <div className="premium-glass p-8 max-w-md w-full text-center space-y-4 border border-rose-500/20">
                    <h2 className="text-xl font-bold text-rose-400">
                        {isVerificationError ? "Email Verification Required" : "Authentication Error"}
                    </h2>
                    <p className="text-sm text-[var(--text-secondary)]">{authError}</p>
                    
                    {isVerificationError && (
                        <div className="text-xs text-[var(--text-muted)] bg-[var(--bg-surface-secondary)] p-3 rounded-lg border border-[var(--border-inner)] space-y-1">
                            {verificationSent ? (
                                <p className="text-emerald-400 font-semibold">✓ Verification email sent! Please check your inbox/spam folder, click the link, and click Retry.</p>
                            ) : (
                                <p>Firebase requires email verification for password accounts. Click below to receive a verification link.</p>
                            )}
                            {verifyError && <p className="text-rose-400">{verifyError}</p>}
                        </div>
                    )}

                    <div className="flex flex-col gap-2 pt-2">
                        {isVerificationError && !verificationSent && (
                            <button 
                                className="btn-primary w-full" 
                                onClick={handleResendVerification}
                                disabled={sendingVerification}
                            >
                                {sendingVerification ? "Sending..." : "Resend Verification Email"}
                            </button>
                        )}
                        <div className="flex gap-3 justify-center">
                            <button className={isVerificationError && !verificationSent ? "btn-secondary flex-1" : "btn-primary flex-1"} onClick={retryAuth}>
                                Retry Connection
                            </button>
                            <button className="btn-secondary flex-1" onClick={logout}>
                                Sign Out
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (!user) {
        return <LoginPage />;
    }

    return (
        <NotificationsProvider>
            <AppMain />
        </NotificationsProvider>
    );
}