function formatNumber(value, language) {
  return new Intl.NumberFormat(language === "tr" ? "tr-TR" : "en-US", {
    maximumFractionDigits: 3,
  }).format(value);
}

export default function AnnualSeriesChart({ series = [], slope, unit = "", language = "en" }) {
  const points = series
    .map((point) => ({ year: Number(point.year), value: Number(point.value) }))
    .filter((point) => Number.isFinite(point.year) && Number.isFinite(point.value))
    .sort((left, right) => left.year - right.year);
  if (!points.length) return null;

  const width = 600;
  const height = 230;
  const margin = { top: 18, right: 18, bottom: 34, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const minYear = points[0].year;
  const maxYear = points[points.length - 1].year;
  const rawMin = Math.min(...points.map((point) => point.value));
  const rawMax = Math.max(...points.map((point) => point.value));
  const padding = (rawMax - rawMin) * 0.12 || Math.max(Math.abs(rawMin) * 0.05, 0.01);
  const minValue = rawMin - padding;
  const maxValue = rawMax + padding;
  const x = (year) => margin.left + (maxYear === minYear ? 0.5 : (year - minYear) / (maxYear - minYear)) * plotWidth;
  const y = (value) => margin.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;
  const segments = [];
  let segment = [];
  points.forEach((point, index) => {
    if (index && point.year - points[index - 1].year !== 1) {
      if (segment.length) segments.push(segment);
      segment = [];
    }
    segment.push(point);
  });
  if (segment.length) segments.push(segment);

  const numericSlope = Number(slope);
  const hasSlope = slope != null && Number.isFinite(numericSlope);
  const intercepts = hasSlope
    ? points.map((point) => point.value - numericSlope * point.year).sort((a, b) => a - b)
    : [];
  const intercept = intercepts.length
    ? intercepts.length % 2
      ? intercepts[(intercepts.length - 1) / 2]
      : (intercepts[intercepts.length / 2 - 1] + intercepts[intercepts.length / 2]) / 2
    : 0;
  const trendLine = hasSlope && points.length > 1
    ? [
      { year: minYear, value: numericSlope * minYear + intercept },
      { year: maxYear, value: numericSlope * maxYear + intercept },
    ]
    : [];
  const tickYears = [...new Set([minYear, Math.round((minYear + maxYear) / 2), maxYear])];
  const tickValues = [minValue, (minValue + maxValue) / 2, maxValue];
  const title = language === "tr" ? "Yıllık zaman serisi" : "Annual time series";
  const trendLabel = language === "tr" ? "Sen eğimi" : "Sen slope";
  const observationLabel = language === "tr" ? "Yıllık gözlem" : "Annual observations";
  const observedLabel = language === "tr" ? "Yıllık değerler" : "Annual values";

  return (
    <figure className="annualSeriesChart">
      <figcaption>
        <strong>{title}</strong>
        <span>{trendLabel}: {hasSlope ? `${formatNumber(numericSlope, language)} ${unit}/yr` : "—"}</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}, ${minYear}–${maxYear}, ${points.length} ${observationLabel.toLowerCase()}`}>
        {tickValues.map((value) => (
          <g key={value}>
            <line x1={margin.left} x2={width - margin.right} y1={y(value)} y2={y(value)} className="annualChartGrid" />
            <text x={margin.left - 8} y={y(value) + 4} textAnchor="end" className="annualChartAxis">{formatNumber(value, language)}</text>
          </g>
        ))}
        <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} className="annualChartAxisLine" />
        {tickYears.map((year) => (
          <text key={year} x={x(year)} y={height - 9} textAnchor="middle" className="annualChartAxis">{year}</text>
        ))}
        {trendLine.length > 0 && (
          <line x1={x(trendLine[0].year)} y1={y(trendLine[0].value)} x2={x(trendLine[1].year)} y2={y(trendLine[1].value)} className="annualChartTrend" />
        )}
        {segments.map((items, index) => (
          <polyline key={index} points={items.map((point) => `${x(point.year)},${y(point.value)}`).join(" ")} className="annualChartSeries" />
        ))}
        {points.map((point) => (
          <circle key={point.year} cx={x(point.year)} cy={y(point.value)} r="3" className="annualChartPoint">
            <title>{point.year}: {formatNumber(point.value, language)} {unit}</title>
          </circle>
        ))}
      </svg>
      <div className="annualChartLegend">
        <span><i className="annualLegendObserved" />{observedLabel}</span>
        {hasSlope && <span><i className="annualLegendTrend" />{language === "tr" ? "Sen eğimi (eğilim çizgisi)" : "Sen slope (trend line)"}</span>}
      </div>
      <small>{points.length} {observationLabel.toLowerCase()} · {minYear}–{maxYear} · {unit}</small>
    </figure>
  );
}
