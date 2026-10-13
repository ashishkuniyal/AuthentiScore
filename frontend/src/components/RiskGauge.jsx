// RiskGauge.jsx — Animated SVG circular gauge (270° arc)
import { getRiskBand } from "../utils/risk";

const RADIUS = 84;
const CX = 100;
const CY = 108;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ≈ 527.79
const ARC_FRACTION = 0.75; // 270° = 75% of full circle
const ARC_LENGTH = CIRCUMFERENCE * ARC_FRACTION; // ≈ 395.84
const GAP_LENGTH = CIRCUMFERENCE - ARC_LENGTH;

function getStrokeGlow(bandKey) {
    switch (bandKey) {
        case "low":
            return { stroke: "#10b981", glow: "rgba(16,185,129,0.35)", badgeClass: "low" };
        case "medium":
            return { stroke: "#f59e0b", glow: "rgba(245,158,11,0.35)", badgeClass: "medium" };
        case "high":
            return { stroke: "#f97316", glow: "rgba(249,115,22,0.35)", badgeClass: "high" };
        case "very_high":
            return { stroke: "#a855f7", glow: "rgba(168,85,247,0.35)", badgeClass: "very-high" };
        default:
            return { stroke: "#94a3b8", glow: "rgba(148,163,184,0.2)", badgeClass: "insufficient" };
    }
}

export default function RiskGauge({ score = null, animated = true }) {
    const isNullScore = score === null || score === undefined || Number.isNaN(Number(score));
    const band = getRiskBand(score);
    const { stroke, glow, badgeClass } = getStrokeGlow(band.key);
    const safeScore = isNullScore ? 0 : Math.min(Math.max(Number(score), 0), 100);
    const fillLength = isNullScore ? 0 : (safeScore / 100) * ARC_LENGTH;

    return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div style={{ position: "relative", width: 200, height: 200 }}>
                <svg viewBox="0 0 200 216" width={200} height={200} style={{ overflow: "visible" }}>
                    <defs>
                        <filter id="gauge-glow" x="-50%" y="-50%" width="200%" height="200%">
                            <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur1" />
                            <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur2" />
                            <feGaussianBlur in="SourceGraphic" stdDeviation="12" result="blur3" />
                            <feMerge>
                                <feMergeNode in="blur3" />
                                <feMergeNode in="blur2" />
                                <feMergeNode in="blur1" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                    </defs>
                    <circle
                        cx={CX}
                        cy={CY}
                        r={RADIUS}
                        fill="none"
                        stroke="var(--border-inner)"
                        strokeWidth={14}
                        strokeLinecap="round"
                        strokeDasharray={`${ARC_LENGTH} ${GAP_LENGTH}`}
                        transform={`rotate(135 ${CX} ${CY})`}
                    />
                    <circle
                        cx={CX}
                        cy={CY}
                        r={RADIUS}
                        fill="none"
                        stroke={stroke}
                        strokeWidth={14}
                        strokeLinecap="round"
                        strokeDasharray={`${ARC_LENGTH} ${GAP_LENGTH}`}
                        strokeDashoffset={ARC_LENGTH - fillLength}
                        transform={`rotate(135 ${CX} ${CY})`}
                        filter="url(#gauge-glow)"
                        style={{
                            transition: animated
                                ? "stroke-dashoffset 1.5s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.6s ease"
                                : "none",
                        }}
                    />
                    <text
                        x={CX}
                        y={CY - 10}
                        textAnchor="middle"
                        dominantBaseline="middle"
                        style={{
                            fontFamily: "var(--font-head)",
                            fontSize: isNullScore ? 28 : 36,
                            fontWeight: 800,
                            fill: stroke,
                            filter: `drop-shadow(0 0 8px ${glow})`,
                        }}
                    >
                        {isNullScore ? "N/A" : safeScore.toFixed(1)}
                    </text>
                    <text
                        x={CX}
                        y={CY + 22}
                        textAnchor="middle"
                        style={{ fontFamily: "var(--font-body)", fontSize: 13, fill: "var(--text-muted)", fontWeight: 500 }}
                    >
                        {isNullScore ? "insufficient data" : "out of 100"}
                    </text>
                </svg>
            </div>
            <span className={`risk-badge ${badgeClass}`} style={{ fontSize: 14, padding: "7px 18px" }}>
                {band.label}
            </span>
        </div>
    );
}
