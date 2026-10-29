import { jsPDF } from "jspdf";
import AnnualSeriesChart from "./AnnualSeriesChart";
import { ANALYSIS_VARIABLES } from "../data/analysisVariables";

function BiodiversityContextCard({ context, language }) {
  const isTurkish = language === "tr";
  const groups = [
    ["birds", isTurkish ? "Kuş kayıtları" : "Bird records"],
    ["mammals", isTurkish ? "Memeli kayıtları" : "Mammal records"],
    ["reptiles", isTurkish ? "Sürüngen kayıtları" : "Reptile records"],
    ["amphibians", isTurkish ? "İki yaşamlı kayıtları" : "Amphibian records"],
    ["fish", isTurkish ? "Balık kayıtları" : "Fish records"],
    ["insects", isTurkish ? "Böcek kayıtları" : "Insect records"],
    ["other_or_unclassified", isTurkish ? "Diğer / sınıflandırılmamış" : "Other / unclassified"],
  ];
  const formatCount = (value) => new Intl.NumberFormat(isTurkish ? "tr-TR" : "en-US").format(value);
  const sourceDisclaimer = isTurkish
    ? "Kaynak: GBIF (NASA verisi değil). Kayıt sayıları popülasyon büyüklüğünü göstermez; gözlem çabasını yansıtır."
    : "Source: GBIF (not NASA data). Record counts do not represent population size; they reflect observation effort.";

  return (
    <section className="biodiversityContextCard" aria-live="polite">
      <header className="biodiversityContextHeader">
        <span>{isTurkish ? "EKOLOJİK VERİ BAĞLAMI" : "ECOLOGICAL DATA CONTEXT"}</span>
        <h3>{isTurkish ? "Biyoçeşitlilik bağlamı" : "Biodiversity context"}</h3>
        {context?.available && (
          <small>{formatCount(context.radius_km)} km · {context.lat}, {context.lon}</small>
        )}
      </header>

      {context?.status === "loading" ? (
        <p className="biodiversityContextMessage">
          {isTurkish ? "GBIF kayıtları yükleniyor…" : "Loading GBIF records…"}
        </p>
      ) : !context?.available ? (
        <p className="biodiversityContextMessage" role="status">
          {isTurkish
            ? "Biyoçeşitlilik verisi şu anda alınamadı. Lütfen daha sonra tekrar deneyin."
            : "Biodiversity data is temporarily unavailable. Please try again later."}
        </p>
      ) : (
        <>
          <div className="biodiversityContextMetrics">
            <div>
              <span>{isTurkish ? "Kayıtlı farklı tür" : "Distinct recorded species"}</span>
              <strong>{formatCount(context.species_count)}{context.species_count_truncated ? "+" : ""}</strong>
            </div>
            <div>
              <span>{isTurkish ? "Tehdit altındaki tür¹" : "Threatened species¹"}</span>
              <strong>{formatCount(context.threatened_species_count)}{context.threatened_species_count_truncated ? "+" : ""}</strong>
            </div>
          </div>
          <div className="biodiversityGroupGrid">
            {groups.map(([key, label]) => (
              <div key={key}>
                <span>{label}</span>
                <strong>{formatCount(context.group_record_counts[key] || 0)}</strong>
              </div>
            ))}
          </div>
          <small className="biodiversityThreatNote">
            ¹ {isTurkish
              ? "VU, EN ve CR kategorilerinde GBIF'e bağlı tür listelerinde yer alan türler."
              : "Species appearing in GBIF-linked checklists with VU, EN, or CR categories."}
          </small>
          {(context.species_count_truncated || context.threatened_species_count_truncated) && (
            <small className="biodiversityThreatNote">
              {isTurkish
                ? "GBIF facet sınırı nedeniyle bu sayı üst sınırdır."
                : "This is a lower-bound count because the GBIF facet limit was reached."}
            </small>
          )}
        </>
      )}

      <p className="biodiversityContextSource">{sourceDisclaimer}</p>
      <a className="biodiversityContextLink" href="https://www.gbif.org/" target="_blank" rel="noreferrer">
        GBIF.org ↗
      </a>
    </section>
  );
}

export default function AnalysisPanel({
  data,
  language = "en",
  mapLayerTitle,
  analysisVariable,
  biodiversityContext,
  regionAnalysisMode = "sampled_boundary_filtered",
  onRegionAnalysisModeChange,
  regionModeAvailable = false,
  canUsePolygonMode = false,
}) {
  const isTurkish = language === "tr";
  if (!data) {
    return (
      <div className="analysisPanel empty">

        <div className="panelEyebrow">
          {isTurkish ? "DÜNYA SİSTEMİ TREND DEDEKTİFİ" : "EARTH SYSTEM TREND DETECTIVE"}
        </div>

        <div className="visualLayerNotice" role="note">
          <strong>{isTurkish ? "NASA GIBS · GÖRSEL KATMAN" : "NASA GIBS · VISUAL LAYER"}</strong>
          <p>
            {isTurkish
              ? `${mapLayerTitle} renkli görüntü sağlar; tek başına sayısal piksel zaman serisi, Sen eğimi veya p-değeri sağlamaz. İstatistik için üst menüden bir analiz değişkeni seçin (${analysisVariable}) ve küreye tıklayın.`
              : `${mapLayerTitle} provides rendered imagery, not a numerical pixel time series, Sen slope, or p-value. To calculate statistics, select an analysis variable from the menu above (${analysisVariable}) and click the globe.`}
          </p>
        </div>

        <h2>
          {isTurkish ? "Bir bölge seçin" : "Select a region"}
        </h2>

        <p>
          {isTurkish ? "Dünyada bir noktaya tıklayın veya çevresel trendi incelemek için bir bölge arayın." : "Click a location on Earth or search for a region to inspect its environmental trend."}
        </p>

        <div className="questionStack">
          <span>01 — {isTurkish ? "NE DEĞİŞİYOR?" : "WHAT IS CHANGING?"}</span>
          <span>02 — {isTurkish ? "NEREDE DEĞİŞİYOR?" : "WHERE IS IT CHANGING?"}</span>
          <span>03 — {isTurkish ? "NE KADAR?" : "HOW MUCH?"}</span>
          <span>04 — {isTurkish ? "ANLAMLI MI?" : "IS IT SIGNIFICANT?"}</span>
        </div>

      </div>
    );
  }

  const {
    name,
    variable,
    stats,
    year,
    analysisEndYear,
    observedStartYear,
    observedEndYear,
    source,
    datasetId,
    datasetDocUrl,
    unit,
    lat,
    lon,
  } = data;
  const reportSource = source;
  const variableDefinition = ANALYSIS_VARIABLES[variable]?.description?.[language] || "";
  const temporalResolution = ANALYSIS_VARIABLES[variable]?.temporalResolution;
  const sourceDocumentationUrl = datasetDocUrl || ANALYSIS_VARIABLES[variable]?.sourceUrl;

  const reportSeries = Array.isArray(data.series) ? data.series : [];
  const verifiedSource = source === "NASA POWER"
    || source?.includes("Google Earth Engine")
    || source === "NASA/JPL Sea Level Change Portal";
  const validObservations = reportSeries.length >= 8 && reportSeries.every((point) =>
    Number.isFinite(Number(point.year)) && Number.isFinite(Number(point.value))
  );
  const reportEndYear = analysisEndYear ?? year;
  const seriesCoversAnalysisPeriod = reportSeries.length > 0
    && Math.max(...reportSeries.map((point) => Number(point.year))) >= Number(reportEndYear);
  const validCoordinates = Number.isFinite(Number(lat)) && Number.isFinite(Number(lon));
  const validStatistics = Number.isFinite(Number(stats?.slope))
    && stats?.slope != null
    && stats?.pValue != null
    && Number.isFinite(Number(stats?.pValue))
    && !["Insufficient Data", "Analysis unavailable", "No verified point series"].includes(stats?.trend);
  const canExportReport = Boolean(
    verifiedSource && datasetId && unit && validObservations && seriesCoversAnalysisPeriod && validCoordinates && validStatistics
  );

  const hasStatistics = stats?.slope != null
    && stats?.pValue != null
    && Number.isFinite(Number(stats.slope))
    && Number.isFinite(Number(stats.pValue));
  const pValue = hasStatistics ? Number(stats.pValue) : null;
  const confidence = !hasStatistics
    ? { label: "INSUFFICIENT DATA", tone: "low", note: "A statistical evidence tier cannot be assigned without a valid time series." }
    : pValue < 0.01
      ? { label: "STRONG EVIDENCE", tone: "high", note: "Strong evidence against no monotonic trend (p < 0.01)." }
      : pValue < 0.05
        ? { label: "STATISTICAL EVIDENCE", tone: "moderate", note: "Evidence against no monotonic trend at p < 0.05." }
        : { label: "NO SIGNIFICANT EVIDENCE", tone: "low", note: "No statistically significant monotonic trend detected; natural variability remains plausible." };
  const localizedConfidence = isTurkish ? {
    ...confidence,
    label: !hasStatistics ? "YETERSİZ VERİ" : confidence.tone === "high" ? "GÜÇLÜ İSTATİSTİKSEL KANIT" : confidence.tone === "moderate" ? "İSTATİSTİKSEL KANIT VAR" : "ANLAMLI KANIT YOK",
    note: !hasStatistics ? "Geçerli zaman serisi olmadan istatistiksel kanıt düzeyi belirlenemez." : confidence.tone === "high" ? "p < 0,01: güçlü kanıt." : confidence.tone === "moderate" ? "p < 0,05: istatistiksel kanıt." : "İstatistiksel olarak anlamlı monoton trend saptanmadı; doğal değişkenlik olası.",
  } : confidence;
  const trendText = (() => {
    const trend = stats?.trend;
    if (!trend) return isTurkish ? "Sonuç yok" : "No result";
    if (trend.toLowerCase() === "insufficient data" || trend.toLowerCase() === "insufficient_data") return isTurkish ? "İstatistiksel test için yetersiz veya aralıklı veri" : "Insufficient or discontinuous data for significance test";
    if (trend.toLowerCase() === "analysis unavailable" || trend.toLowerCase() === "no verified point series") return isTurkish ? "Analiz verisi alınamadı" : "Analysis data unavailable";
    if (trend.toLowerCase() === "no trend" || trend === "No clear trend") {
      return isTurkish ? "İstatistiksel olarak anlamlı monoton trend saptanmadı" : "No statistically significant monotonic trend detected";
    }
    const increasing = trend.toLowerCase().includes("increas");
    const decreasing = trend.toLowerCase().includes("decreas");
    const direction = increasing
      ? (isTurkish ? "Artış" : "Increase")
      : decreasing
        ? (isTurkish ? "Azalış" : "Decrease")
        : trend;
    const significant = stats?.significant ?? Number(stats?.pValue) < 0.05;
    if (isTurkish) return significant ? `Anlamlı ${direction}` : `${direction} (istatistiksel olarak anlamlı değil)`;
    return significant ? `Significant ${direction}` : `${direction} (not statistically significant)`;
  })();
  const formatPValue = (value) => {
    if (value == null || value === "") return "—";
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return "—";
    if (numericValue < 0.00001) return isTurkish ? "<0,00001" : "<0.00001";
    return new Intl.NumberFormat(isTurkish ? "tr-TR" : "en-US", {
      maximumSignificantDigits: 5,
    }).format(numericValue);
  };

  function exportBriefing(reportType = "full") {
    if (!canExportReport) return;
    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    const series = reportSeries;
    const values = series.map((point) => point.value);
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 1);
    const range = max - min || 1;
    const title = reportType === "jury" ? "JURY ONE-PAGER" : reportType === "appendix" ? "DATA APPENDIX" : "SCIENTIFIC BRIEFING";
    const text = (value, x, y, options) => pdf.text(String(value), x, y, options);

    pdf.setFillColor(16, 46, 58);
    pdf.rect(0, 0, 210, 34, "F");
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(18);
    text(`TWIN EARTH / ${title}`, 16, 16);
    pdf.setFontSize(9);
    text(`Earth System Trend Analysis | ${new Date().toLocaleDateString()}`, 16, 25);
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(10);
    text(`${name} | ${variable} | ${observedStartYear ?? 2002}-${reportEndYear}`, 16, 43);
    text(`Coordinates: ${Number(lat).toFixed(4)}°, ${Number(lon).toFixed(4)}°`, 16, 49);
    text(`Verified source: ${reportSource}`, 16, 55);
    text(`Dataset: ${datasetId} | Unit: ${unit} | Annual observations: ${series.length}`, 16, 61, { maxWidth: 178 });
    pdf.setFontSize(14);
    pdf.setTextColor(23, 107, 125);
    text("Executive finding", 16, 73);
    pdf.setFontSize(10);
    pdf.setTextColor(20, 35, 43);
    text(`${stats?.trend || "Unresolved trend"}. Evidence tier: ${confidence.label.toLowerCase()}.`, 16, 81);

    const evidenceTier = confidence.tone === "high" ? "HIGH" : confidence.tone === "moderate" ? "MODERATE" : "NONE";
    const cards = [["Sen's slope", `${stats?.slope ?? "-"} /yr`], ["MK Z-score", stats?.zScore ?? "-"], ["p-value", formatPValue(stats?.pValue)], ["Evidence tier", evidenceTier]];
    cards.forEach(([label, value], index) => {
      const x = 16 + index * 45;
      pdf.setDrawColor(184, 201, 207);
      pdf.setFillColor(245, 250, 251);
      pdf.rect(x, 91, 41, 23, "FD");
      pdf.setTextColor(92, 112, 120);
      pdf.setFontSize(7);
      text(label, x + 3, 98);
      pdf.setTextColor(20, 35, 43);
      pdf.setFontSize(9);
      text(value, x + 3, 107);
    });

    if (reportType !== "jury") {
      pdf.setTextColor(23, 107, 125);
      pdf.setFontSize(14);
      text("Observed trajectory", 16, 128);
      pdf.setDrawColor(150, 175, 181);
      pdf.line(22, 174, 190, 174);
      pdf.line(22, 134, 22, 174);
      pdf.setDrawColor(239, 127, 66);
      pdf.setLineWidth(0.8);
      series.forEach((point, index) => {
        if (!index) return;
        const previous = series[index - 1];
        const x1 = 22 + ((index - 1) / Math.max(series.length - 1, 1)) * 168;
        const x2 = 22 + (index / Math.max(series.length - 1, 1)) * 168;
        const y1 = 174 - ((previous.value - min) / range) * 38;
        const y2 = 174 - ((point.value - min) / range) * 38;
        pdf.line(x1, y1, x2, y2);
        pdf.setFillColor(239, 127, 66);
        pdf.circle(x2, y2, 1, "F");
      });
      pdf.setTextColor(23, 107, 125);
      pdf.setFontSize(14);
      text("Annual magnitude", 16, 194);
      series.forEach((point, index) => {
        const barWidth = Math.max(3, 150 / Math.max(series.length, 1));
        const height = ((point.value - min) / range) * 25;
        pdf.setFillColor(40, 127, 145);
        pdf.rect(22 + index * (150 / Math.max(series.length, 1)), 229 - height, barWidth, height, "F");
      });
    }

    const confidenceY = reportType === "jury" ? 130 : 240;
    pdf.setTextColor(23, 107, 125);
    pdf.setFontSize(14);
    text("Confidence assessment", 16, confidenceY);
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(10);
    text(`${confidence.label}: ${confidence.note}`, 16, confidenceY + 10, { maxWidth: 175 });
    text("Decision threshold: p < 0.05. This evidence tier is not a probability that the trend is true.", 16, confidenceY + 19, { maxWidth: 178 });

    if (reportType !== "jury") {
      pdf.addPage();
      pdf.setFillColor(16, 46, 58);
      pdf.rect(0, 0, 210, 28, "F");
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(15);
      text("DATA APPENDIX / ANNUAL OBSERVATIONS", 16, 17);
      pdf.setTextColor(20, 35, 43);
      pdf.setFontSize(9);
      text(`${name} | ${Number(lat).toFixed(4)}°, ${Number(lon).toFixed(4)}° | ${source}`, 16, 38, { maxWidth: 178 });
      pdf.setTextColor(23, 107, 125);
      pdf.setFontSize(8);
      pdf.setFillColor(220, 235, 237);
      pdf.rect(16, 46, 178, 8, "F");
      text(`YEAR          VALUE (${unit})          YEAR-OVER-YEAR CHANGE`, 19, 52);
      pdf.setTextColor(20, 35, 43);
      let tableY = 61;
      series.forEach((point, index) => {
        const delta = index ? (point.value - series[index - 1].value).toFixed(3) : "-";
        if (tableY > 278) {
          pdf.addPage();
          tableY = 20;
        }
        text(`${point.year}          ${point.value}          ${delta}`, 19, tableY);
        tableY += 6;
      });
    }

    pdf.setTextColor(102, 128, 138);
    pdf.setFontSize(8);
    text(`${reportSource} observations; derived statistics are estimates, not a guarantee of 100% accuracy.`, 16, 286, { maxWidth: 178 });
    pdf.save(`TwinEarth-${title.toLowerCase().replaceAll(" ", "-")}-${name.replaceAll(/[^a-z0-9]+/gi, "-")}.pdf`);
  }

  return (
    <div className="analysisPanel">

      <div className="panelEyebrow">
        {isTurkish ? "DÜNYA SİSTEMİ TREND ANALİZİ" : "EARTH SYSTEM TREND ANALYSIS"}
      </div>

      <div className="visualLayerNotice" role="note">
        <strong>{isTurkish ? "GIBS GÖRÜNTÜSÜ ≠ SAYISAL ANALİZ" : "GIBS IMAGE ≠ NUMERICAL ANALYSIS"}</strong>
        <p>
          {isTurkish
            ? `${mapLayerTitle} yalnızca görsel katmandır; aşağıdaki ${variable} istatistikleri ${source || "seçili veri kaynağı"} zaman serisinden hesaplanır. Harita görüntüsünden türetilmez.`
            : `${mapLayerTitle} is a visual layer only. The ${variable} statistics below use the ${source || "selected data source"} time series; they are not derived from the map image.`}
        </p>
      </div>

      {regionModeAvailable && <div className="regionAnalysisMode">
        <label htmlFor="regionAnalysisMode">
          {isTurkish ? "BÖLGESEL ANALİZ YÖNTEMİ" : "REGIONAL ANALYSIS METHOD"}
        </label>
        <select
          id="regionAnalysisMode"
          value={regionAnalysisMode}
          onChange={(event) => onRegionAnalysisModeChange?.(event.target.value)}
        >
          <option value="sampled_boundary_filtered">
            {isTurkish ? "Hızlı tahmin (sınır-filtreli örnekleme, ≤16 nokta)" : "Fast estimate (boundary-filtered sampling, ≤16 points)"}
          </option>
          <option value="polygon_area_weighted" disabled={!canUsePolygonMode}>
            {isTurkish ? "Poligon analizi (alan ağırlıklı)" : "Polygon analysis (area-weighted)"}
          </option>
        </select>
        {!canUsePolygonMode && <small>{isTurkish
          ? "Poligon analizi GeoJSON sınırı ve GEE değişkeni gerektirir. NASA POWER ve deniz seviyesi hızlı örneklemeyi kullanır."
          : "Polygon analysis requires a GeoJSON boundary and a GEE variable. NASA POWER and sea level use fast sampling."}</small>}
      </div>}

      <div className="pdfActions">
        <button className="briefingButton" disabled={!canExportReport} title={!canExportReport ? (isTurkish ? "PDF için doğrulanmış kaynak, koordinat, istatistik ve en az 8 gözlem gerekir." : "PDF requires a verified source, coordinates, statistics, and at least 8 observations.") : undefined} onClick={() => exportBriefing("full")}>▣ {isTurkish ? "TAM BİLİMSEL BRİFİNG PDF" : "FULL SCIENTIFIC BRIEFING PDF"}</button>
        <button className="briefingButton secondary" disabled={!canExportReport} title={!canExportReport ? (isTurkish ? "PDF için doğrulanmış kaynak ve yeterli veri gerekir." : "PDF requires a verified source and sufficient data.") : undefined} onClick={() => exportBriefing("appendix")}>▤ {isTurkish ? "VERİ EKİ PDF" : "DATA APPENDIX PDF"}</button>
        <button className="briefingButton secondary" disabled={!canExportReport} title={!canExportReport ? (isTurkish ? "PDF için doğrulanmış kaynak ve yeterli veri gerekir." : "PDF requires a verified source and sufficient data.") : undefined} onClick={() => exportBriefing("jury")}>◉ {isTurkish ? "JÜRİ TEK SAYFA PDF" : "JURY ONE-PAGER PDF"}</button>
      </div>
      {!canExportReport && <small className="pdfGateNote">{isTurkish ? "Rapor beklemede: doğrulanmış kaynak, koordinat ve istatistiklerin yanı sıra en az 8 geçerli gözlem gerekir." : "Report unavailable: a verified source, coordinates, statistics, and at least 8 valid observations are required."}</small>}

      <div className="analysisTitleRow">

        <div>
          <h2>{name}</h2>
          <span className="analysisPeriod">
            {observedStartYear ?? "2002"} → {observedEndYear ?? "—"}
          </span>
          {observedEndYear != null && observedEndYear < year && (
            <small className="coverageNote">
              {isTurkish ? `Seçili yıl ${year}; bu kaynakta son gözlem ${observedEndYear}.` : `Selected ${year}; latest observation from this source is ${observedEndYear}.`}
            </small>
          )}
        </div>

        <span className="variableBadge">
          {variable}
        </span>

      </div>

      {variableDefinition && <small className="coverageNote variableDefinition">{variableDefinition}</small>}

      <small className="coverageNote">
        {isTurkish
          ? `İstatistik dönemi: ${observedStartYear ?? "—"}–${observedEndYear ?? "—"} · Geçerli yıllık gözlem: ${reportSeries.length} · Birim: ${unit || "—"}`
          : `Statistics period: ${observedStartYear ?? "—"}–${observedEndYear ?? "—"} · Valid annual observations: ${reportSeries.length} · Unit: ${unit || "—"}`}
      </small>
      {temporalResolution && <small className="coverageNote">
        {isTurkish ? `Kaynak zaman çözünürlüğü: ${temporalResolution}. İstatistikler yıllık seriden hesaplanır.` : `Source temporal resolution: ${temporalResolution}. Statistics use the annual series.`}
      </small>}
      {data.aggregationLabel && <small className="coverageNote">
        {isTurkish ? `Yıllık işlem: ${data.aggregationLabel}${data.elapsedSeconds != null ? ` · Hesaplama: ${data.elapsedSeconds} sn` : ""}` : `Annual aggregation: ${data.aggregationLabel}${data.elapsedSeconds != null ? ` · Calculation: ${data.elapsedSeconds} s` : ""}`}
      </small>}
      {data.regionMode && <small className="coverageNote">
        {isTurkish
          ? `Yöntem: ${data.method === "polygon_area_weighted_single_cell" ? "poligon merkez-hücresi yedeği" : data.method === "polygon_area_weighted" ? "poligon alan-ağırlıklı" : "sınır-filtreli örnekleme"}${data.method?.startsWith("polygon_area_weighted") ? ` · Geçerli piksel/yıl: ${data.validPixelCountRange?.min ?? 0}–${data.validPixelCountRange?.max ?? 0} (en az ${data.validPixelCount ?? 0})` : ` · Kullanılan örnek nokta: ${data.regionSampleCount ?? 0}/16`}`
          : `Method: ${data.method === "polygon_area_weighted_single_cell" ? "polygon center-cell fallback" : data.method === "polygon_area_weighted" ? "polygon area-weighted" : "boundary-filtered sampling"}${data.method?.startsWith("polygon_area_weighted") ? ` · Valid pixels/year: ${data.validPixelCountRange?.min ?? 0}–${data.validPixelCountRange?.max ?? 0} (minimum ${data.validPixelCount ?? 0})` : ` · Sample points used: ${data.regionSampleCount ?? 0}/16`}`}
      </small>}
      {data.resolutionWarning && <small className="coverageNote" role="status">{data.resolutionWarning}</small>}
      {data.lowCoverageYears?.length > 0 && <small className="coverageNote" role="status">
        {isTurkish
          ? `Düşük piksel kapsamı (<3 geçerli piksel): ${data.lowCoverageYears.join(", ")}. Bu yılları temkinli yorumlayın.`
          : `Low pixel coverage (&lt;3 valid pixels): ${data.lowCoverageYears.join(", ")}. Interpret these years cautiously.`}
      </small>}
      {(data.missingYearWarning || data.missingYears?.length > 0) && <small className="coverageNote" role="status">
        {isTurkish
          ? `Eksik yıllar (${(data.missingYears || []).join(", ") || "—"}); Mann–Kendall anlamlılık sonucu verilmedi.`
          : data.missingYearWarning || `Missing annual observations: ${(data.missingYears || []).join(", ")}; Mann–Kendall significance was withheld.`}
      </small>}
      {data.shortSeriesWarning && <small className="coverageNote" role="status">
        {isTurkish
          ? "Seri 15 yıldan kısa; istatistiksel olarak anlamlı bir trend saptamak için daha uzun dönem gerekebilir."
          : "The series is shorter than 15 years; a longer record may be needed to detect a statistically significant trend."}
      </small>}
      {data.regionMode && !data.shortSeriesWarning && reportSeries.length < 15 && <small className="coverageNote" role="status">
        {isTurkish
          ? "Seri 15 yıldan kısa; istatistiksel olarak anlamlı bir trend saptamak için daha uzun dönem gerekebilir."
          : "The series is shorter than 15 years; a longer record may be needed to detect a statistically significant trend."}
      </small>}
      {data.regionMode && <small className="coverageNote">
        {data.method?.startsWith("polygon_area_weighted")
          ? (data.method === "polygon_area_weighted_single_cell"
            ? (isTurkish
              ? "Poligon çözünürlüğü kaynak hücresinden küçük veya alan paydası boştu; mevcut yıllarda merkez hücresi kullanıldı."
              : "The polygon is below source-cell resolution or had an empty area denominator; center-cell values were used where available.")
            : isTurkish
            ? "Yıllık değer, görüntü maskesiyle sınırlı geçerli piksel alanlarıyla ağırlıklandırıldı."
            : "Each annual value is weighted by valid pixel area after applying the source mask.")
          : (isTurkish
            ? `Bölgesel tahmin, sınır içinde kalan en fazla 16 örnek noktanın enlem alan ağırlıklarıyla birleştirilmesidir; tam poligon alan ortalaması değildir.`
            : `Regional estimate combines up to 16 points inside the boundary using latitude-area weights; it is not a full polygon area mean.`)}
      </small>}
      {data.regionMethodNote && <small className="coverageNote" role="status">{data.regionMethodNote}</small>}
      {variable === "GRACE Total Water Storage Anomaly" && <small className="coverageNote">
        {isTurkish
          ? "GRACE burada yerçekimi değişiminden türetilen toplam kara su kütlesi anomalisi ölçer (cm su eşdeğeri). Türkiye’deki azalış buz kaybı anlamına gelmez; su depolamasındaki değişimi yansıtır."
          : "GRACE measures total terrestrial water-mass anomaly inferred from gravity changes (cm water equivalent). A decline in Türkiye does not mean ice loss; it reflects changes in stored water."}
      </small>}

      {data.coverageMessage && <small className="coverageNote" role="status">{data.coverageMessage}</small>}
      {data.errorMessage && <small className="coverageNote" role="status">{data.errorMessage}</small>}
      {stats?.message && <small className="coverageNote" role="status">{stats.message}</small>}

      <AnnualSeriesChart
        series={reportSeries}
        slope={stats?.slope}
        unit={unit || ""}
        language={language}
      />

      <div className="questionLabel">
        {isTurkish ? "NE DEĞİŞİYOR?" : "WHAT IS CHANGING?"}
      </div>

      <div className="resultMain">
        {trendText || (isTurkish ? "Sonuç yok" : "No result")}
      </div>

      <div className="analysisGrid">

        <div className="infoCard">
          <span>{isTurkish ? "Sen eğimi" : "Sen's slope"}</span>
          <strong>
            {stats?.slope ?? "—"} /yr
          </strong>
        </div>

        <div className="infoCard">
          <span>Mann-Kendall Z</span>
          <strong>
            {stats?.zScore ?? "—"}
          </strong>
        </div>

        <div className="infoCard">
          <span>p-değeri</span>
          <strong>
            {formatPValue(stats?.pValue)}
          </strong>
        </div>

        <div className="infoCard">
          <span>{isTurkish ? "Yön" : "Direction"}</span>
          <strong>
            {!hasStatistics
              ? "—"
              : stats?.slope > 0
              ? (isTurkish ? "ARTIYOR" : "INCREASING")
              : stats?.slope < 0
              ? (isTurkish ? "AZALIYOR" : "DECREASING")
              : (isTurkish ? "YOK" : "NONE")}
          </strong>
        </div>

      </div>

      <div className="significanceBox">

        <span>
          {isTurkish ? "İSTATİSTİKSEL ANLAMLILIK" : "STATISTICAL SIGNIFICANCE"}
        </span>

        <strong>
          {!hasStatistics
            ? (isTurkish ? "YETERSİZ VERİ" : "INSUFFICIENT DATA")
            : (stats?.significant ?? pValue < 0.05)
            ? (isTurkish ? "ANLAMLI" : "SIGNIFICANT")
            : (isTurkish ? "ANLAMSIZ" : "NOT SIGNIFICANT")}
        </strong>

        <small>
          {isTurkish ? "Eşik: p < 0.05" : "Threshold: p < 0.05"}
        </small>

      </div>

      <div className={`confidenceCard ${localizedConfidence.tone}`}>
        <div className="confidenceTop"><span>{isTurkish ? "İSTATİSTİKSEL KANIT DÜZEYİ" : "STRENGTH OF STATISTICAL EVIDENCE"}</span><strong>{localizedConfidence.label}</strong></div>
        <div className={`confidenceScale ${localizedConfidence.tone}`} aria-label={localizedConfidence.label}><span /><span /><span /></div>
        <small>{localizedConfidence.note}</small>
      </div>

      <div className="scienceNote">

          <strong>{isTurkish ? "Yöntem" : "Method"}</strong>

        <p>
          {isTurkish
            ? `Hamed–Rao düzeltmeli Mann–Kendall testi monoton trend kanıtını değerlendirir; Sen eğimi değişim hızını ölçer. ${mapLayerTitle ? `Haritadaki ${mapLayerTitle} renkleri seçili görüntü değerlerini gösterir; tek başına zaman içindeki değişimi veya anlamlı trendi kanıtlamaz.` : ""} Analiz, seçili değişkenin koordinattaki yıllık serisine uygulanır.`
            : `The Hamed–Rao modified Mann–Kendall test evaluates evidence for a monotonic trend; Sen's slope estimates its rate. ${mapLayerTitle ? `Map colors in ${mapLayerTitle} show selected image values; they do not by themselves establish change over time or a significant trend.` : ""} The test uses the selected variable's annual series at the chosen coordinate.`}
        </p>

      </div>

      <div className="dataStatus">
        {language === "tr" ? "VERİ KAYNAĞI" : "DATA SOURCE"}
        <span>
          {source || "NASA DATASET CONNECTION"}
        </span>
        {datasetId && <small>{datasetId}</small>}
        {sourceDocumentationUrl && (
          <a href={sourceDocumentationUrl} target="_blank" rel="noreferrer">
            {isTurkish ? "Veri ürünü belgeleri ↗" : "Dataset documentation ↗"}
          </a>
        )}
      </div>

      <BiodiversityContextCard context={biodiversityContext} language={language} />

    </div>
  );
}
