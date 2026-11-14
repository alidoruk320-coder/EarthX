function formatNumber(value, language) {
  return new Intl.NumberFormat(language === "tr" ? "tr-TR" : "en-US", {
    maximumFractionDigits: 3,
  }).format(value);
}

function formatDate(value, language, options = { month: "short", year: "numeric" }) {
  return new Intl.DateTimeFormat(language === "tr" ? "tr-TR" : "en-US", options)
    .format(new Date(value));
}

export default function ObservationSeriesChart({
  series = [],
  unit = "",
  language = "en",
  trendlineStartValue,
  trendlineEndValue,
}) {
  const points = series
    .map((point) => ({ ...point, timestamp: Date.parse(point.date), value: Number(point.value) }))
    .filter((point) => Number.isFinite(point.timestamp) && Number.isFinite(point.value))
    .sort((left, right) => left.timestamp - right.timestamp);
  if (!points.length) return null;

  const width = 600;
  const height = 230;
  const margin = { top: 18, right: 18, bottom: 36, left: 62 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const firstTime = points[0].timestamp;
  const lastTime = points[points.length - 1].timestamp;
  const values = points.map((point) => point.value);
  const hasTrendline = trendlineStartValue != null
    && trendlineEndValue != null
    && Number.isFinite(Number(trendlineStartValue))
    && Number.isFinite(Number(trendlineEndValue))
    && lastTime > firstTime;
  const rangeValues = hasTrendline
    ? [...values, Number(trendlineStartValue), Number(trendlineEndValue)]
    : values;
  const rawMin = Math.min(...rangeValues);
  const rawMax = Math.max(...rangeValues);
  const padding = (rawMax - rawMin) * 0.12 || Math.max(Math.abs(rawMin) * 0.05, 0.01);
  const minValue = rawMin - padding;
  const maxValue = rawMax + padding;
  const x = (timestamp) => margin.left + (
    lastTime === firstTime ? 0.5 : (timestamp - firstTime) / (lastTime - firstTime)
  ) * plotWidth;
  const y = (value) => margin.top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;
  const tickDates = [...new Set([firstTime, points[Math.floor(points.length / 2)].timestamp, lastTime])];
  const tickValues = [minValue, (minValue + maxValue) / 2, maxValue];
  const title = language === "tr" ? "SWOT uydu geçiş gözlemleri" : "SWOT satellite overpass observations";
  const countLabel = language === "tr" ? "geçerli gözlem" : "valid observations";

  return (
    <figure className="observationSeriesChart">
      <figcaption>
        <strong>{title}</strong>
        <span>{language === "tr"
          ? "Noktalar düzensiz geçişlerdir; kesikli çizgi betimleyici Sen eğimidir"
          : "Dots are irregular overpasses; dashed line is the descriptive Sen slope"}</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${title}, ${formatDate(points[0].date, language)}–${formatDate(points[points.length - 1].date, language)}, ${points.length} ${countLabel}`}
      >
        {tickValues.map((value) => (
          <g key={value}>
            <line x1={margin.left} x2={width - margin.right} y1={y(value)} y2={y(value)} className="observationChartGrid" />
            <text x={margin.left - 8} y={y(value) + 4} textAnchor="end" className="annualChartAxis">
              {formatNumber(value, language)}
            </text>
          </g>
        ))}
        <line x1={margin.left} x2={width - margin.right} y1={height - margin.bottom} y2={height - margin.bottom} className="annualChartAxisLine" />
        {tickDates.map((timestamp) => (
          <text key={timestamp} x={x(timestamp)} y={height - 9} textAnchor="middle" className="annualChartAxis">
            {formatDate(timestamp, language)}
          </text>
        ))}
        {hasTrendline && (
          <line
            x1={x(firstTime)}
            y1={y(Number(trendlineStartValue))}
            x2={x(lastTime)}
            y2={y(Number(trendlineEndValue))}
            className="observationChartTrend"
          />
        )}
        {points.map((point, index) => (
          <circle
            key={`${point.date}-${index}`}
            cx={x(point.timestamp)}
            cy={y(point.value)}
            r="3"
            className="observationChartPoint"
          >
            <title>
              {`${formatDate(point.date, language, { dateStyle: "medium", timeStyle: "short" })}: ${formatNumber(point.value, language)} ${unit}; uncertainty=${point.uncertainty ?? "—"} m; quality_f=${point.quality_f ?? "—"}; ice_clim_f=${point.ice_clim_f ?? "—"}; ice_dyn_f=${point.ice_dyn_f ?? "—"}`}
            </title>
          </circle>
        ))}
      </svg>
      <small>
        {points.length} {countLabel} · {formatDate(points[0].date, language)}–{formatDate(points[points.length - 1].date, language)} · {unit}
      </small>
    </figure>
  );
}
