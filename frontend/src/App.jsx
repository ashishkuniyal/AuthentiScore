import { useState, useEffect } from "react";
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
import { useAuth } from "./context/AuthContext";
import "./App.css";

export default function App() {
    const { user, loading } = useAuth();
    const [activeTab, setActiveTab] = useState("dashboard");
    const [notifications, setNotifications] = useState([]);
    const [globalSearchQuery, setGlobalSearchQuery] = useState("");

    // Setup WebSocket connection
    useEffect(() => {
        const ws = new WebSocket("ws://localhost:8000/ws/notifications");
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setNotifications(prev => [data, ...prev].slice(0, 50));
        };
        
        return () => ws.close();
    }, []);

    if (loading) {
        return <div style={{ height: "100vh", background: "var(--bg-app)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-secondary)" }}>Loading AuthentiScore...</div>;
    }

    if (!user) {
        return <LoginPage />;
    }

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