// src/utils/risk.js
// Single source of truth for risk bands and styling across AuthentiScore (F5 / C5)
// Bands: <34 Low Risk, <67 Medium Risk, <90 High Risk, >=90 Very High Risk

export const RISK_BANDS = {
    LOW: { max: 34, key: "low", label: "Low Risk", shortLabel: "Low", color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
    MEDIUM: { max: 67, key: "medium", label: "Medium Risk", shortLabel: "Medium", color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/30" },
    HIGH: { max: 90, key: "high", label: "High Risk", shortLabel: "High", color: "text-rose-400", bg: "bg-rose-500/10", border: "border-rose-500/30" },
    VERY_HIGH: { max: 101, key: "very_high", label: "Very High Risk", shortLabel: "Critical", color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/30" },
    INSUFFICIENT: { key: "insufficient_data", label: "Insufficient Data", shortLabel: "N/A", color: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/30" },
};

export function getRiskBand(score, backendRiskLevel = null) {
    if (backendRiskLevel) {
        const norm = String(backendRiskLevel).toLowerCase();
        if (norm === "low") return RISK_BANDS.LOW;
        if (norm === "medium") return RISK_BANDS.MEDIUM;
        if (norm === "high") return RISK_BANDS.HIGH;
        if (norm === "very_high" || norm === "critical") return RISK_BANDS.VERY_HIGH;
        if (norm.includes("insufficient")) return RISK_BANDS.INSUFFICIENT;
    }

    if (score === null || score === undefined || Number.isNaN(Number(score))) {
        return RISK_BANDS.INSUFFICIENT;
    }

    const numeric = Number(score);
    if (numeric < 34) return RISK_BANDS.LOW;
    if (numeric < 67) return RISK_BANDS.MEDIUM;
    if (numeric < 90) return RISK_BANDS.HIGH;
    return RISK_BANDS.VERY_HIGH;
}

export function classifyRisk(score, backendRiskLevel = null) {
    return getRiskBand(score, backendRiskLevel).label;
}

export function getRiskLabel(score, backendRiskLevel = null) {
    return getRiskBand(score, backendRiskLevel).label;
}

export function getRiskColor(score, backendRiskLevel = null) {
    return getRiskBand(score, backendRiskLevel).color;
}

export function getRiskBadgeClasses(score, backendRiskLevel = null) {
    const band = getRiskBand(score, backendRiskLevel);
    return `${band.color} ${band.bg} ${band.border}`;
}

export function isSuspicious(score, backendRiskLevel = null) {
    const band = getRiskBand(score, backendRiskLevel);
    return band.key === "high" || band.key === "very_high";
}

export function isAuthentic(score, backendRiskLevel = null) {
    const band = getRiskBand(score, backendRiskLevel);
    return band.key === "low";
}

export const RISK_FILTER_OPTIONS = [
    { value: "all", label: "All Risk Levels" },
    { value: "low", label: "Low Risk (< 34%)" },
    { value: "medium", label: "Medium Risk (34–66%)" },
    { value: "high", label: "High Risk (67–89%)" },
    { value: "very_high", label: "Very High Risk (≥ 90%)" },
    { value: "insufficient_data", label: "Insufficient Data" },
];
