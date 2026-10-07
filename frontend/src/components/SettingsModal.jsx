import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { X, Save, Camera, Mail, User } from "lucide-react";

export default function SettingsModal({ onClose }) {
    const { user, updateUserProfile } = useAuth();
    const [name, setName] = useState(user?.full_name || "");
    const [photoURL, setPhotoURL] = useState(user?.photoURL || "");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);

    const handleSave = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError("");
        setSuccess(false);

        try {
            await updateUserProfile(name, photoURL);
            setSuccess(true);
            setTimeout(() => {
                onClose();
            }, 1000);
        } catch (err) {
            setError(err.message || "Failed to update profile");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            position: "fixed", top: 0, left: 0, width: "100%", height: "100%", 
            background: "rgba(0,0,0,0.7)", backdropFilter: "blur(5px)",
            display: "flex", alignItems: "center", justifyContent: "center", 
            zIndex: 9999
        }} className="animate-fade-in">
            <div style={{
                background: "var(--bg-card)", border: "1px solid var(--border-inner)", 
                borderRadius: 16, width: "100%", maxWidth: 500, padding: 30,
                boxShadow: "var(--shadow-lg)"
            }} className="animate-slide-up">
                
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
                    <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>Profile Settings</h2>
                    <button 
                        onClick={onClose}
                        style={{ background: "var(--btn-secondary-bg)", border: "1px solid var(--btn-secondary-border)", color: "var(--text-secondary)", width: 32, height: 32, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", transition: "all 0.2s" }}
                        onMouseEnter={e => e.currentTarget.style.background = "var(--btn-secondary-hover-bg)"}
                        onMouseLeave={e => e.currentTarget.style.background = "var(--btn-secondary-bg)"}
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Avatar Preview */}
                <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
                    <div style={{ position: "relative" }}>
                        {photoURL ? (
                            <img src={photoURL} alt="Avatar" style={{ width: 80, height: 80, borderRadius: "50%", objectFit: "cover", border: "2px solid var(--border-inner)" }} />
                        ) : (
                            <div style={{ width: 80, height: 80, borderRadius: "50%", background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}>
                                <User size={32} />
                            </div>
                        )}
                        <div style={{ position: "absolute", bottom: 0, right: 0, background: "var(--bg-surface)", border: "1px solid var(--border-inner)", width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-primary)" }}>
                            <Camera size={14} />
                        </div>
                    </div>
                </div>

                <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                    <div>
                        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>Email Address (Read-only)</label>
                        <div style={{ position: "relative" }}>
                            <Mail size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
                            <input
                                type="text"
                                value={user?.email || ""}
                                className="input-field"
                                style={{ paddingLeft: 40, opacity: 0.5, cursor: "not-allowed" }}
                                disabled
                            />
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>Display Name</label>
                        <div style={{ position: "relative" }}>
                            <User size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                className="input-field"
                                style={{ paddingLeft: 40 }}
                                placeholder="Enter your name"
                                disabled={loading}
                            />
                        </div>
                    </div>

                    <div>
                        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>Avatar Image URL</label>
                        <div style={{ position: "relative" }}>
                            <Camera size={16} color="var(--text-muted)" style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
                            <input
                                type="text"
                                value={photoURL}
                                onChange={(e) => setPhotoURL(e.target.value)}
                                className="input-field"
                                style={{ paddingLeft: 40 }}
                                placeholder="https://example.com/my-photo.jpg"
                                disabled={loading}
                            />
                        </div>
                        <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>Paste a link to an image to use as your profile picture.</p>
                    </div>

                    {error && (
                        <div style={{ padding: "12px", background: "rgba(220,38,38,0.1)", border: "1px solid rgba(220,38,38,0.3)", borderRadius: 10, fontSize: 13, color: "#ef4444", fontWeight: 500 }}>
                            {error}
                        </div>
                    )}

                    {success && (
                        <div style={{ padding: "12px", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", borderRadius: 10, fontSize: 13, color: "#10b981", fontWeight: 500 }}>
                            Profile updated successfully!
                        </div>
                    )}

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 10 }}>
                        <button type="button" onClick={onClose} style={{ padding: "0 16px", height: 40, borderRadius: 8, background: "var(--bg-surface-secondary)", border: "1px solid var(--border-inner)", color: "var(--text-primary)", fontSize: 14, fontWeight: 500, cursor: "pointer" }}>
                            Cancel
                        </button>
                        <button type="submit" className="btn-primary" style={{ padding: "0 24px", height: 40, borderRadius: 8, display: "flex", alignItems: "center", gap: 8 }} disabled={loading}>
                            {loading ? "Saving..." : <><Save size={16} /> Save Changes</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
