// src/utils/trendEngine.js

export function calculateTrend(dataPoints) {
    const n = dataPoints.length;
    if (n < 3) {
        return {
            trend: "Insufficient Data",
            slope: 0,
            zScore: 0,
            pValue: 1.0,
            significant: false
        };
    }

    // 1. Sen's Slope Calculation
    const slopes = [];
    for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
            const slope = (dataPoints[j].value - dataPoints[i].value) / (dataPoints[j].year - dataPoints[i].year);
            slopes.push(slope);
        }
    }
    slopes.sort((a, b) => a - b);
    const mid = Math.floor(slopes.length / 2);
    const sensSlope = slopes.length % 2 !== 0 ? slopes[mid] : (slopes[mid - 1] + slopes[mid]) / 2;

    // 2. Mann-Kendall Trend Test
    let s = 0;
    for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
            s += Math.sign(dataPoints[j].value - dataPoints[i].value);
        }
    }

    const varS = (n * (n - 1) * (2 * n + 5)) / 18;
    let z = 0;
    if (s > 0) {
        z = (s - 1) / Math.sqrt(varS);
    } else if (s < 0) {
        z = (s + 1) / Math.sqrt(varS);
    }

    const pValue = 2 * (1 - standardNormalCDF(Math.abs(z)));
    const isSignificant = pValue < 0.05;

    let trendDir = "No clear trend";
    if (sensSlope > 0 && isSignificant) trendDir = "Significant Increase (↑)";
    else if (sensSlope < 0 && isSignificant) trendDir = "Significant Decrease (↓)";
    else if (sensSlope > 0) trendDir = "Increasing (Non-significant)";
    else if (sensSlope < 0) trendDir = "Decreasing (Non-significant)";

    return {
        trend: trendDir,
        slope: Number(sensSlope.toFixed(4)),
        zScore: Number(z.toFixed(2)),
        pValue: Number(pValue.toFixed(4)),
        significant: isSignificant
    };
}

function standardNormalCDF(z) {
    const t = 1 / (1 + 0.2316419 * Math.abs(z));
    const d = 0.3989423 * Math.exp(-z * z / 2);
    let probability = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
    if (z > 0) {
        probability = 1 - probability;
    }
    return probability;
}

// Simülasyon Zaman Serisi Üreteci (NASA Gaps & Observations)
export function generateTimeSeries(variable, startYear = 2002, endYear = 2026) {
    const series = [];
    let base = 50;
    let trendFactor = 0.2;

    if (variable === "Temperature") { base = 14.5; trendFactor = 0.03; }
    else if (variable === "Ice Mass") { base = 3000; trendFactor = -15.2; }
    else if (variable === "NDVI / Vegetation") { base = 0.65; trendFactor = -0.003; }
    else if (variable === "Sea Level") { base = 0; trendFactor = 3.4; }

    for (let yr = startYear; yr <= endYear; yr++) {
        const noise = (Math.random() - 0.5) * (Math.abs(trendFactor) * 3 || 1);
        const val = base + (yr - startYear) * trendFactor + noise;
        series.push({ year: yr, value: Number(val.toFixed(2)) });
    }
    return series;
}