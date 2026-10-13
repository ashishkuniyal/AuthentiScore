import React from 'react';
import { X, AlertTriangle, ShieldCheck, Cpu, Users } from 'lucide-react';
import RiskGauge from './RiskGauge';

export default function ProfileDeepAuditModal({ profile, onClose }) {
    if (!profile) return null;

    const { identifier, platform, score, classification, top_ml_factors, nlp_signals, features } = profile;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-[var(--bg-surface)] border border-[var(--border-outer)] rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
                
                {/* Header */}
                <div className="flex justify-between items-center p-6 border-b border-[var(--border-inner)] sticky top-0 bg-[var(--bg-surface)] z-10">
                    <div>
                        <h2 className="text-2xl font-bold font-heading flex items-center gap-3">
                            <Users className="text-[var(--accent)]" size={28} />
                            Deep Audit: {identifier}
                        </h2>
                        <p className="text-[var(--text-secondary)] text-sm mt-1 uppercase tracking-wider">{platform}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-[var(--bg-surface-secondary)] rounded-full transition-colors">
                        <X size={24} />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
                    
                    {/* Left Column: Score & Profile Stats */}
                    <div className="flex flex-col gap-6">
                        <div className="card text-center py-8">
                            <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-6">AI Risk Analysis</h3>
                            <div className="flex justify-center mb-4">
                                <RiskGauge score={score} classification={classification} size="lg" />
                            </div>
                        </div>

                        {features && (
                            <div className="card">
                                <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-4 border-b border-[var(--border-inner)] pb-2">Profile Metrics</h3>
                                <div className="space-y-3 text-sm">
                                    <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Followers:</span> <span className="font-mono">{features.followers ?? 'N/A'}</span></div>
                                    <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Following:</span> <span className="font-mono">{features.following ?? 'N/A'}</span></div>
                                    <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Posts:</span> <span className="font-mono">{features.posts ?? 'N/A'}</span></div>
                                    <div className="flex justify-between"><span className="text-[var(--text-secondary)]">Private:</span> <span>{features.is_private ? 'Yes' : 'No'}</span></div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right Column: SHAP & NLP */}
                    <div className="lg:col-span-2 flex flex-col gap-6">
                        
                        {/* Explainable AI / SHAP Values */}
                        <div className="card">
                            <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-4 border-b border-[var(--border-inner)] pb-2 flex items-center gap-2">
                                <Cpu size={18} className="text-[var(--accent)]" /> Explainable AI (SHAP)
                            </h3>
                            {(!top_ml_factors || top_ml_factors.length === 0) ? (
                                <p className="text-[var(--text-secondary)] italic text-sm py-4">No AI explanations available for this profile.</p>
                            ) : (
                                <div className="space-y-4">
                                    {top_ml_factors.map((factor, idx) => {
                                        const isRisk = factor.is_risk;
                                        const colorClass = isRisk ? 'text-[var(--risk-high)] bg-[rgba(239,68,68,0.1)]' : 'text-[var(--risk-low)] bg-[rgba(16,185,129,0.1)]';
                                        const barColor = isRisk ? 'bg-[var(--risk-high)]' : 'bg-[var(--risk-low)]';
                                        // Normalize width for visual representation (max 0.3 SHAP scale typically)
                                        const width = Math.min(Math.max((Math.abs(factor.shap_value) / 0.3) * 100, 5), 100);

                                        return (
                                            <div key={idx} className="flex flex-col gap-1">
                                                <div className="flex justify-between text-sm items-end">
                                                    <span className="font-medium text-[var(--text-primary)]">{factor.label}</span>
                                                    <span className={`text-xs px-2 py-0.5 rounded font-bold ${colorClass}`}>
                                                        {factor.impact.toUpperCase()}
                                                    </span>
                                                </div>
                                                <div className="w-full h-2 bg-[var(--bg-surface-secondary)] rounded-full overflow-hidden flex">
                                                    {isRisk ? (
                                                        <div className={`h-full ${barColor} ml-auto`} style={{ width: `${width}%` }} />
                                                    ) : (
                                                        <div className={`h-full ${barColor}`} style={{ width: `${width}%` }} />
                                                    )}
                                                </div>
                                                <div className="text-xs text-[var(--text-secondary)] mt-1 opacity-70">
                                                    Feature: <code className="bg-[var(--bg-surface-secondary)] px-1 rounded">{factor.feature}</code> (Value: {factor.value})
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* NLP Analysis */}
                        <div className="card">
                            <h3 className="text-sm font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-4 border-b border-[var(--border-inner)] pb-2">NLP Bio Analysis</h3>
                            {!features?.bio ? (
                                <p className="text-[var(--text-secondary)] italic text-sm">No bio available for analysis.</p>
                            ) : (
                                <div>
                                    <div className="bg-[var(--bg-surface-secondary)] p-4 rounded-lg text-sm italic border-l-4 border-[var(--accent)] mb-4">
                                        "{features.bio}"
                                    </div>
                                    
                                    {nlp_signals?.matched_categories?.length > 0 ? (
                                        <div className="flex flex-wrap gap-2">
                                            {nlp_signals.matched_categories.map((cat, idx) => (
                                                <span key={idx} className="flex items-center gap-1 bg-[rgba(239,68,68,0.1)] text-[var(--risk-high)] border border-[rgba(239,68,68,0.2)] px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">
                                                    <AlertTriangle size={12} /> {cat}
                                                </span>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-2 text-[var(--risk-low)] text-sm font-bold">
                                            <ShieldCheck size={18} /> No suspicious language detected.
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>

                    </div>
                </div>

            </div>
        </div>
    );
}
