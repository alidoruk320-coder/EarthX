import { jsPDF } from "jspdf";
import AnnualSeriesChart from "./AnnualSeriesChart";
import { ANALYSIS_VARIABLES } from "../data/analysisVariables";
import ObservationSeriesChart from "./ObservationSeriesChart";

function formatObservationDate(value, language) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(language === "tr" ? "tr-TR" : "en-US", {
    dateStyle: "medium",
  }).format(new Date(value));
}

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
  analysisRange,
  analysisRangeBounds,
  onAnalysisRangeChange,
  polygonAggregationMode = "annual",
  onPolygonAggregationModeChange,
}) {
  const isTurkish = language === "tr";
  const quickRegionEstimateDisabled = analysisVariable === "Soil Moisture";
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
  const temporalResolution = data.temporalResolution || ANALYSIS_VARIABLES[variable]?.temporalResolution;
  const sourceDocumentationUrl = datasetDocUrl || ANALYSIS_VARIABLES[variable]?.sourceUrl;
  const observationSeries = data.observationSeries === true;

  const reportSeries = Array.isArray(data.series) ? data.series : [];
  const repeatedValuePairs = reportSeries.slice(1).flatMap((point, index) => {
    const previous = reportSeries[index];
    return Number(point.value) === Number(previous.value)
      ? [`${previous.year}–${point.year}`]
      : [];
  });
  const supportedSource = source?.startsWith("NASA POWER")
    || source?.includes("Google Earth Engine")
    || source?.startsWith("NASA PO.DAAC Hydrocron")
    || source === "NOAA CoastWatch blended satellite altimetry"
    || source === "NASA/JPL Sea Level Change Portal";
  const modelOutput = data.modelOutput === true;
  const validObservations = reportSeries.length >= 8 && reportSeries.every((point) =>
    point.year != null && point.year !== "" && point.value != null && point.value !== ""
    && Number.isFinite(Number(point.year)) && Number.isFinite(Number(point.value))
  );
  const continuousAnnualSeries = validObservations && reportSeries.every((point, index) =>
    index === 0 || Number(point.year) === Number(reportSeries[index - 1].year) + 1
  );
  const reportEndYear = analysisEndYear ?? year;
  const seriesCoversAnalysisPeriod = reportSeries.length > 0
    && Math.max(...reportSeries.map((point) => Number(point.year))) >= Number(reportEndYear);
  const validCoordinates = Number.isFinite(Number(lat)) && Number.isFinite(Number(lon));
  const polygonCalculationWarning = Boolean(
    data.regionMode && (data.method === "polygon_area_weighted" || data.method === "polygon_area_weighted_single_cell")
  );
  const validStatistics = Number.isFinite(Number(stats?.slope))
    && stats?.slope != null
    && stats?.pValue != null
    && Number.isFinite(Number(stats?.pValue))
    && !["Insufficient Data", "Analysis unavailable", "No verified point series"].includes(stats?.trend);
  const canExportReport = Boolean(
    supportedSource && datasetId && unit && continuousAnnualSeries && seriesCoversAnalysisPeriod && validCoordinates && validStatistics
  );

  const hasStatistics = stats?.slope != null
    && stats?.pValue != null
    && Number.isFinite(Number(stats.slope))
    && Number.isFinite(Number(stats.pValue));
  const pValue = hasStatistics ? Number(stats.pValue) : null;
  const confidence = observationSeries
    ? {
        label: "DESCRIPTIVE ONLY",
        tone: "low",
        note: "The descriptive Sen slope summarizes the observed series; no inferential test or significance claim is made.",
      }
    : !hasStatistics
    ? {
        label: stats?.testStatus === "unavailable" ? "TEST UNAVAILABLE" : "INSUFFICIENT DATA",
        tone: "low",
        note: stats?.message || "A statistical evidence tier cannot be assigned without a valid test result.",
      }
    : pValue < 0.01
      ? { label: "STRONG EVIDENCE", tone: "high", note: "Strong evidence against no monotonic trend (p < 0.01)." }
      : pValue < 0.05
        ? { label: "STATISTICAL EVIDENCE", tone: "moderate", note: "Evidence against no monotonic trend at p < 0.05." }
        : { label: "NO SIGNIFICANT EVIDENCE", tone: "low", note: "No statistically significant monotonic trend detected; natural variability remains plausible." };
  const localizedConfidence = isTurkish ? {
    ...confidence,
    label: observationSeries
      ? "YALNIZCA GÖZLEM"
      : !hasStatistics
      ? stats?.testStatus === "unavailable" ? "TEST HESAPLANAMADI" : "YETERSİZ VERİ"
      : confidence.tone === "high" ? "GÜÇLÜ İSTATİSTİKSEL KANIT" : confidence.tone === "moderate" ? "İSTATİSTİKSEL KANIT VAR" : "ANLAMLI KANIT YOK",
    note: observationSeries
      ? "Sen eğimi gözlenen serinin betimleyici özetidir; p-değeri veya istatistiksel anlamlılık göstermez."
      : !hasStatistics
      ? stats?.testStatus === "unavailable"
        ? (isTurkish ? "Geçerli test istatistikleri alınamadığı için kanıt düzeyi belirlenemedi." : "Evidence cannot be assigned because valid test statistics are unavailable.")
        : (isTurkish ? "Geçerli istatistiksel test sonucu olmadan kanıt düzeyi belirlenemez." : "A statistical evidence tier cannot be assigned without a valid test result.")
      : confidence.tone === "high" ? "p < 0,01: güçlü kanıt." : confidence.tone === "moderate" ? "p < 0,05: istatistiksel kanıt." : "İstatistiksel olarak anlamlı monoton trend saptanmadı; doğal değişkenlik olası.",
  } : confidence;
  const trendText = (() => {
    const trend = stats?.trend;
    if (observationSeries) {
      if (stats?.slope == null || !Number.isFinite(Number(stats.slope))) {
        return isTurkish
          ? "Betimleyici trend için yeterli zaman aralıklı SWOT gözlemi yok"
          : "Not enough time-separated SWOT observations for a descriptive trend";
      }
      const direction = stats.slope > 0
        ? (isTurkish ? "yükseliyor" : "increasing")
        : stats.slope < 0
          ? (isTurkish ? "düşüyor" : "decreasing")
          : (isTurkish ? "belirgin değişim yok" : "no net change");
      return isTurkish
        ? `Betimleyici Sen eğimi: ${direction}`
        : `Descriptive Sen trend: ${direction}`;
    }
    if (!trend) return isTurkish ? "Sonuç yok" : "No result";
    if (modelOutput) {
      return isTurkish
        ? "Model çıktısı: eğim gösterilir, istatistiksel anlamlılık değerlendirilmez."
        : "Model output: slope shown; statistical significance is not assessed.";
    }
    if (!hasStatistics || stats?.testStatus === "unavailable") {
      return isTurkish ? "İstatistiksel test hesaplanamadı" : "Statistical test could not be calculated";
    }
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

  function exportBriefing() {
    if (!canExportReport) return;
    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    const series = reportSeries;
    const values = series.map((point) => point.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const text = (value, x, y, options) => pdf.text(String(value), x, y, options);
    const methodDescription = !data.regionMode
      ? "Point analysis at the selected coordinate."
      : data.method === "polygon_area_weighted"
        ? "Area-weighted mean of valid source-grid pixels intersecting the selected polygon, calculated separately for each year."
        : data.method === "polygon_area_weighted_single_cell"
          ? "The polygon is smaller than a source grid cell (or has no valid area-weighted pixels); the source cell at its center is used. This is not a full polygon area mean."
        : data.method === "bounding_box_fallback"
          ? `Approximate regional estimate from ${data.regionSampleCount ?? 0} points in a search bounding box because no boundary polygon was available.`
          : `Approximate regional estimate from ${data.regionSampleCount ?? 0} boundary-filtered sample points; this is not a full polygon pixel-area reduction.`;
    const reportNotes = [
      data.sourceUsed && `Dataset used: ${data.sourceUsed}.`,
      data.scaleUsed != null && `Polygon analysis scale: ${data.scaleUsed} m.`,
      data.geometrySimplifyMeters != null && `Geometry simplification tolerance: ${data.geometrySimplifyMeters} m.`,
      data.aggregationLabel && `Annual aggregation: ${data.aggregationLabel}.`,
      data.temporalResolution && `Source cadence: ${data.temporalResolution}.`,
      data.regionMethodNote,
      data.resolutionWarning,
      data.sourceWarning,
      data.coverageMessage,
      data.missingYearWarning,
      data.lowCoverageYears?.length > 0
        && `Low pixel coverage (<3 valid pixels): ${data.lowCoverageYears.join(", ")}.`,
      data.shortSeriesWarning,
      repeatedValuePairs.length > 0
        && `Identical adjacent annual summaries: ${repeatedValuePairs.join(", ")}. Identical values alone are not evidence of a trend.`,
    ].filter(Boolean);

    pdf.setFillColor(16, 46, 58);
    pdf.rect(0, 0, 210, 34, "F");
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(18);
    text("TWIN EARTH / SCIENTIFIC BRIEFING", 16, 16);
    pdf.setFontSize(9);
    text(`Earth System Trend Analysis | ${new Date().toLocaleDateString()}`, 16, 25);
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(10);
    text(`${name} | ${variable} | observed years: ${observedStartYear}-${observedEndYear}`, 16, 43, { maxWidth: 178 });
    text(`${data.regionMode ? "Region bounding-box midpoint" : "Point coordinate"}: ${Number(lat).toFixed(4)}°, ${Number(lon).toFixed(4)}°`, 16, 49);
    text(`Data source: ${reportSource}`, 16, 55);
    text(`Dataset: ${datasetId} | Unit: ${unit} | Annual observations: ${series.length}`, 16, 61, { maxWidth: 178 });
    pdf.setFontSize(14);
    pdf.setTextColor(23, 107, 125);
    text("Executive finding", 16, 73);
    pdf.setFontSize(10);
    pdf.setTextColor(20, 35, 43);
    text(`${stats?.trend || "Unresolved trend"}. Statistical evidence label: ${confidence.label.toLowerCase()}.`, 16, 81, { maxWidth: 178 });

    const evidenceTier = confidence.tone === "high" ? "HIGH" : confidence.tone === "moderate" ? "MODERATE" : "NOT SIGNIFICANT";
    const cards = [["Sen's slope", `${stats?.slope ?? "-"} ${unit}/year`], ["Hamed-Rao MK Z", stats?.zScore ?? "-"], ["p-value", formatPValue(stats?.pValue)], ["Evidence tier", evidenceTier]];
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
      text(value, x + 3, 107, { maxWidth: 35 });
    });

    pdf.setTextColor(23, 107, 125);
    pdf.setFontSize(14);
    text(`Observed annual trajectory (${unit})`, 16, 128);
    pdf.setDrawColor(150, 175, 181);
    pdf.line(22, 174, 190, 174);
    pdf.line(22, 134, 22, 174);
    pdf.setDrawColor(239, 127, 66);
    pdf.setLineWidth(0.8);
    series.forEach((point, index) => {
      const x = 22 + (index / Math.max(series.length - 1, 1)) * 168;
      const y = 174 - ((point.value - min) / range) * 38;
      if (index > 0) {
        const previous = series[index - 1];
        const previousX = 22 + ((index - 1) / Math.max(series.length - 1, 1)) * 168;
        const previousY = 174 - ((previous.value - min) / range) * 38;
        pdf.line(previousX, previousY, x, y);
      }
      pdf.setFillColor(239, 127, 66);
      pdf.circle(x, y, 1, "F");
    });
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(8);
    text(String(observedStartYear), 22, 181);
    text("Year", 102, 181);
    text(String(observedEndYear), 184, 181);

    const confidenceY = 198;
    pdf.setTextColor(23, 107, 125);
    pdf.setFontSize(14);
    text("Statistical evidence", 16, confidenceY);
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(10);
    text(`${confidence.label}: ${confidence.note}`, 16, confidenceY + 10, { maxWidth: 175 });
    text("Decision threshold: p < 0.05. This evidence tier is not a probability that the trend is true.", 16, confidenceY + 19, { maxWidth: 178 });

    pdf.addPage();
    const addAppendixHeader = (title) => {
      pdf.setFillColor(16, 46, 58);
      pdf.rect(0, 0, 210, 28, "F");
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(15);
      text(title, 16, 17);
    };
    addAppendixHeader("METHOD, LIMITATIONS & ANNUAL OBSERVATIONS");
    pdf.setTextColor(20, 35, 43);
    pdf.setFontSize(9);
    let appendixY = 37;
    const addWrappedNote = (label, value) => {
      const lines = pdf.splitTextToSize(`${label}: ${value}`, 178);
      const requiredHeight = lines.length * 4 + 3;
      if (appendixY + requiredHeight > 276) {
        pdf.addPage();
        addAppendixHeader("METHOD & DATA NOTES (CONTINUED)");
        appendixY = 37;
      }
      pdf.text(lines, 16, appendixY);
      appendixY += requiredHeight;
    };
    addWrappedNote("Spatial method", methodDescription);
    addWrappedNote("Trend method", "Sen's slope estimates the rate of change per year. The Hamed-Rao modified Mann-Kendall test evaluates monotonic-trend evidence; significance is assessed at p < 0.05.");
    reportNotes.forEach((note) => addWrappedNote("Data note", note));

    const addTableHeader = () => {
      pdf.setFillColor(220, 235, 237);
      pdf.rect(16, appendixY, 178, 8, "F");
      pdf.setTextColor(23, 107, 125);
      pdf.setFontSize(8);
      text(`YEAR                 VALUE (${unit})                 YEAR-ON-YEAR CHANGE`, 19, appendixY + 6);
      appendixY += 14;
      pdf.setTextColor(20, 35, 43);
      pdf.setFontSize(8);
    };
    if (appendixY + 24 > 276) {
      pdf.addPage();
      addAppendixHeader("ANNUAL OBSERVATIONS");
      appendixY = 37;
    }
    addTableHeader();
    series.forEach((point, index) => {
      if (appendixY > 276) {
        pdf.addPage();
        addAppendixHeader("ANNUAL OBSERVATIONS (CONTINUED)");
        appendixY = 37;
        addTableHeader();
      }
      const delta = index ? Number(point.value) - Number(series[index - 1].value) : null;
      text(`${point.year}                 ${String(point.value)}                 ${delta == null ? "-" : String(delta)}`, 19, appendixY);
      appendixY += 5;
    });

    pdf.setTextColor(102, 128, 138);
    pdf.setFontSize(8);
    const footer = "Descriptive analysis only; it does not establish causation. A p-value is not the probability that a trend is true.";
    for (let page = 1; page <= pdf.getNumberOfPages(); page += 1) {
      pdf.setPage(page);
      text(footer, 16, 286, { maxWidth: 178 });
    }
    pdf.save(`TwinEarth-scientific-briefing-${name.replaceAll(/[^a-z0-9]+/gi, "-")}.pdf`);
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

      {polygonCalculationWarning && (
        <div className="polygonProcessingNotice" role="status">
          <strong>{isTurkish ? "LÜTFEN BEKLEYİNİZ" : "PLEASE WAIT"}</strong>
          <span>
            {variable === "Total Column Ozone"
              ? isTurkish
                ? "Ozon poligon alan analizi hesaplanıyor; bu işlem yaklaşık 1,5 dakika sürebilir."
                : "Ozone polygon area analysis is running; this step may take about 1.5 minutes."
              : isTurkish
                ? "Poligon analizi hesaplaması çok daha ağırdır; bu işlem yaklaşık 1 dakika sürebilir."
                : "Polygon analysis is much heavier to compute; this step may take about 1 minute."}
          </span>
        </div>
      )}

      {regionModeAvailable && <div className="regionAnalysisMode">
        <label htmlFor="regionAnalysisMode">
          {isTurkish ? "BÖLGESEL ANALİZ YÖNTEMİ" : "REGIONAL ANALYSIS METHOD"}
        </label>
        {quickRegionEstimateDisabled ? (
          <>
            <select
              id="regionAnalysisMode"
              value={regionAnalysisMode === "sampled_boundary_filtered" ? "polygon_area_weighted" : regionAnalysisMode}
              onChange={(event) => onRegionAnalysisModeChange?.(event.target.value)}
              disabled={!canUsePolygonMode}
            >
              <option value="polygon_area_weighted">
                {isTurkish ? "Poligon analizi (alan ağırlıklı)" : "Polygon analysis (area-weighted)"}
              </option>
            </select>
            <small>
              {isTurkish
                ? "Bu veri için hızlı sınır tahmini kapatılmıştır; Google Earth Engine çok yıllık örnekleme isteklerinde bellek sınırına düşmektedir."
                : "Fast boundary estimates are disabled for this variable because Google Earth Engine exceeds memory limits on multi-year sampling requests."}
            </small>
          </>
        ) : (
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
        )}
        {!canUsePolygonMode && <small>{isTurkish
          ? "Poligon analizi GeoJSON sınırı ve GEE değişkeni gerektirir. NASA POWER ve deniz seviyesi hızlı örneklemeyi kullanır."
          : "Polygon analysis requires a GeoJSON boundary and a GEE variable. NASA POWER and sea level use fast sampling."}</small>}
      </div>}
      {analysisRange && analysisRangeBounds && !observationSeries && <div className="regionAnalysisMode statisticalYearRange">
        <label>{isTurkish ? "İSTATİSTİK ARALIĞI (TAMAMLANMIŞ YILLAR)" : "STATISTICAL RANGE (COMPLETED YEARS)"}</label>
        <div className="analysisYearInputs">
          <select aria-label={isTurkish ? "Başlangıç yılı" : "Start year"} value={analysisRange[0]} onChange={(event) => {
            const nextStart = Number(event.target.value);
            onAnalysisRangeChange?.([nextStart, Math.max(nextStart, Number(analysisRange[1]))]);
          }}>
            {Array.from({ length: analysisRangeBounds[1] - analysisRangeBounds[0] + 1 }, (_, index) => analysisRangeBounds[0] + index).map((yearValue) => <option key={yearValue} value={yearValue}>{yearValue}</option>)}
          </select>
          <span>→</span>
          <select aria-label={isTurkish ? "Bitiş yılı" : "End year"} value={analysisRange[1]} onChange={(event) => {
            const nextEnd = Number(event.target.value);
            onAnalysisRangeChange?.([Math.min(Number(analysisRange[0]), nextEnd), nextEnd]);
          }}>
            {Array.from({ length: analysisRangeBounds[1] - analysisRangeBounds[0] + 1 }, (_, index) => analysisRangeBounds[0] + index).map((yearValue) => <option key={yearValue} value={yearValue}>{yearValue}</option>)}
          </select>
        </div>
        <small>{isTurkish ? "Harita zaman kaydırıcısı yalnızca görüntü yılını değiştirir." : "The map timeline changes imagery year only."}</small>
      </div>}
      {regionAnalysisMode === "polygon_area_weighted" && canUsePolygonMode
        && variable === "Soil Moisture"
        && <div className="regionAnalysisMode">
          <label htmlFor="polygonAggregationMode">{isTurkish ? "POLİGON ZAMANSAL TOPLAMA" : "POLYGON TEMPORAL AGGREGATION"}</label>
          <select id="polygonAggregationMode" value={polygonAggregationMode} onChange={(event) => onPolygonAggregationModeChange?.(event.target.value)}>
            <option value="annual">{isTurkish ? "Mevcut yıllık yol" : "Existing annual path"}</option>
            <option value="monthly_server_batch">{isTurkish ? "Sunucu tarafında aylık toplu yol (deneysel)" : "Server-side monthly batch (experimental)"}</option>
          </select>
          <small>{isTurkish ? "Deneysel yolun bellek ve süre davranışı bölge/batch boyutuna bağlıdır." : "The experimental path's memory and runtime depend on region and batch size."}</small>
        </div>}

      <div className="pdfActions">
        <button className="briefingButton" disabled={!canExportReport} title={!canExportReport ? (isTurkish ? "PDF için kaynak, koordinat, istatistik ve en az 8 kesintisiz yıllık gözlem gerekir." : "PDF requires a source, coordinates, statistics, and at least 8 consecutive annual observations.") : undefined} onClick={exportBriefing}>▣ {isTurkish ? "TAM BİLİMSEL BRİFİNG PDF" : "FULL SCIENTIFIC BRIEFING PDF"}</button>
      </div>
      {!canExportReport && <small className="pdfGateNote">{isTurkish ? "Rapor beklemede: kaynak, koordinat ve istatistiklerin yanı sıra en az 8 kesintisiz yıllık gözlem gerekir." : "Report unavailable: a source, coordinates, statistics, and at least 8 consecutive annual observations are required."}</small>}

      <div className="analysisTitleRow">

        <div>
          <h2>{name}</h2>
          <span className="analysisPeriod">
            {observationSeries
              ? `${formatObservationDate(data.observedStartDate, language)} → ${formatObservationDate(data.observedEndDate, language)}`
              : `${observedStartYear ?? data.analysisStartYear ?? analysisRange?.[0] ?? "—"} → ${observedEndYear ?? data.analysisEndYear ?? analysisRange?.[1] ?? "—"}`}
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

      {data.regionType && <small className="coverageNote">
        {isTurkish ? `Bölge türü: ${data.regionType}${data.boundarySource ? ` · Sınır kaynağı: ${data.boundarySource}` : ""}` : `Region type: ${data.regionType}${data.boundarySource ? ` · Boundary source: ${data.boundarySource}` : ""}`}
      </small>}
      {data.displayYearNote && <div className="dataQualityAlert displayYearNote" role="note">
        <strong>{isTurkish ? "ZAMAN KAYDIRICISI VE İSTATİSTİK" : "TIMELINE YEAR AND STATISTICS"}</strong>
        <p>{data.displayYearNote}</p>
      </div>}
      {data.boundaryWarning && <div className="dataQualityAlert" role="alert">
        <strong>{isTurkish ? "SINIR POLİGONU BULUNAMADI" : "BOUNDARY POLYGON UNAVAILABLE"}</strong>
        <p>{isTurkish
          ? "Analiz bounding box içindeki örnek noktalara dayanır; ülke/il alan ortalaması değildir."
          : "Analysis uses sample points inside the search bounding box; it is not a country or administrative-area mean."}</p>
      </div>}
      {data.partialYearExcluded?.length > 0 && <div className="dataQualityAlert" role="note">
        <strong>{isTurkish ? "İLK KISMİ YIL TREND DIŞINDA" : "PARTIAL FIRST YEAR EXCLUDED"}</strong>
        <p>{isTurkish
          ? `${data.partialYearExcluded.join(", ")} yılı ürün kaydının yıl içinde başlaması nedeniyle trend hesabına alınmadı${data.firstFullYear ? `; ilk tam yıl ${data.firstFullYear}` : ""}.`
          : `${data.partialYearExcluded.join(", ")} was excluded from the trend because the product record begins partway through that year${data.firstFullYear ? `; first full year: ${data.firstFullYear}` : ""}.`}</p>
      </div>}

      {variableDefinition && <small className="coverageNote variableDefinition">{variableDefinition}</small>}

      <small className="coverageNote">
        {observationSeries
          ? isTurkish
            ? `Gözlem dönemi: ${formatObservationDate(data.observedStartDate, language)}–${formatObservationDate(data.observedEndDate, language)} · Geçerli SWOT geçiş gözlemi: ${reportSeries.length} · Birim: ${unit || "—"}`
            : `Observation period: ${formatObservationDate(data.observedStartDate, language)}–${formatObservationDate(data.observedEndDate, language)} · Valid SWOT overpasses: ${reportSeries.length} · Unit: ${unit || "—"}`
          : isTurkish
            ? `İstatistik dönemi: ${observedStartYear ?? "—"}–${observedEndYear ?? "—"} · Geçerli yıllık gözlem: ${reportSeries.length} · Birim: ${unit || "—"}`
            : `Statistics period: ${observedStartYear ?? "—"}–${observedEndYear ?? "—"} · Valid annual observations: ${reportSeries.length} · Unit: ${unit || "—"}`}
      </small>
      {temporalResolution && <small className="coverageNote">
        {observationSeries
          ? isTurkish
            ? `Kaynak zaman çözünürlüğü: ${temporalResolution}. Zaman serisi yıllık ortalamaya dönüştürülmez.`
            : `Source temporal resolution: ${temporalResolution}. Observations are not converted to annual averages.`
          : isTurkish
            ? `Kaynak zaman çözünürlüğü: ${temporalResolution}. İstatistikler yıllık seriden hesaplanır.`
            : `Source temporal resolution: ${temporalResolution}. Statistics use the annual series.`}
      </small>}
      {data.locationSelectionDistanceKm != null && <small className="coverageNote">
        {isTurkish
          ? `En yakın desteklenen göl özelliğine uzaklık: ${data.locationSelectionDistanceKm} km`
          : `Distance to nearest supported lake feature: ${data.locationSelectionDistanceKm} km`}
      </small>}
      {data.cacheUpdatedAt && <small className="coverageNote">
        {isTurkish
          ? `SWOT önbelleği son güncelleme: ${formatObservationDate(data.cacheUpdatedAt, language)}`
          : `SWOT cache last refreshed: ${formatObservationDate(data.cacheUpdatedAt, language)}`}
      </small>}
      {data.aggregationLabel && <small className="coverageNote">
        {isTurkish ? `Yıllık işlem: ${data.aggregationLabel}${data.elapsedSeconds != null ? ` · Hesaplama: ${data.elapsedSeconds} sn` : ""}` : `Annual aggregation: ${data.aggregationLabel}${data.elapsedSeconds != null ? ` · Calculation: ${data.elapsedSeconds} s` : ""}`}
      </small>}
      {data.aggregationMode === "monthly_server_batch" && <small className="coverageNote" role="note">
        {isTurkish
          ? `Aylık sunucu tarafı yol · ${data.serverBatchYears || 1} yıllık blok · Bu yöntem canlı olarak GEE'de ölçülmeden performans garantisi taşımaz.`
          : `Server-side monthly path · ${data.serverBatchYears || 1}-year blocks · Runtime is not guaranteed until measured against live GEE.`}
      </small>}
      {data.missingMonths?.length > 0 && <div className="dataQualityAlert" role="status">
        <strong>{isTurkish ? "EKSİK AYLIK GÖZLEMLER" : "MISSING MONTHLY OBSERVATIONS"}</strong>
        <p>{data.missingMonths.join(", ")}</p>
      </div>}
      {data.scaleUsed != null && <small className="coverageNote">
        {isTurkish ? `Ölçek: ${Number(data.scaleUsed).toLocaleString("tr-TR")} m` : `Scale: ${Number(data.scaleUsed).toLocaleString("en-US")} m`}
      </small>}
      {data.inputBoundarySimplified && <small className="coverageNote" role="note">
        {isTurkish
          ? "Çok ayrıntılı NDVI sınırı, GEE isteğini küçültmek için yaklaşık 0,002° toleransla sadeleştirildi; bu işlem kaynak raster çözünürlüğünü değiştirmez."
          : "The high-detail NDVI boundary was simplified at approximately 0.002° tolerance to reduce the GEE request; this does not change source raster resolution."}
      </small>}
      {data.sourceUsed && <small className="coverageNote">
        {isTurkish ? `Kullanılan ürün: ${data.sourceUsed}` : `Product used: ${data.sourceUsed}`}
      </small>}
      {data.regionMode && <small className="coverageNote">
        {isTurkish
          ? `Yöntem: ${data.method === "bounding_box_fallback" ? "bounding box örneklemesi" : data.method === "polygon_area_weighted_single_cell" ? "poligon merkez-hücresi yedeği" : data.method === "polygon_area_weighted" ? "poligon alan-ağırlıklı" : "sınır-filtreli örnekleme"}${data.method?.startsWith("polygon_area_weighted") ? ` · Geçerli piksel/yıl: ${data.validPixelCountRange?.min ?? 0}–${data.validPixelCountRange?.max ?? 0} (en az ${data.validPixelCount ?? 0})` : ` · Kullanılan örnek nokta: ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16}`}`
          : `Method: ${data.method === "bounding_box_fallback" ? "bounding-box sampling" : data.method === "polygon_area_weighted_single_cell" ? "polygon center-cell fallback" : data.method === "polygon_area_weighted" ? "polygon area-weighted" : "boundary-filtered sampling"}${data.method?.startsWith("polygon_area_weighted") ? ` · Valid pixels/year: ${data.validPixelCountRange?.min ?? 0}–${data.validPixelCountRange?.max ?? 0} (minimum ${data.validPixelCount ?? 0})` : ` · Sample points used: ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16}`}`}
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
      {data.pointRetrievalInfo && <div className="coverageNote" role="status">
        {data.pointRetrievalInfo.method === "monthly_means_sequential_single_year_requests"
          ? (isTurkish
            ? `MERRA-2 veri alma: yıl yıl sıralı istek · aylık ortalamalardan yıllık değer · ${data.pointRetrievalInfo.requestCount ?? "—"} Earth Engine isteği${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} sn` : ""}.`
            : `MERRA-2 retrieval: sequential single-year requests · annual values from monthly means · ${data.pointRetrievalInfo.requestCount ?? "—"} Earth Engine requests${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} s` : ""}.`)
          : data.pointRetrievalInfo.method === "getRegion_single_request_monthly_then_annual_mean"
          ? (isTurkish
            ? `Nokta veri alma: tek Earth Engine isteği · 3 saatlik SMAP görüntüleri önce aylık, sonra yıllık ortalamaya indirildi · ${data.pointRetrievalInfo.observationCount ?? "—"} geçerli yıllık bileşik${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} sn` : ""}.`
            : `Point retrieval: one Earth Engine request · 3-hourly SMAP images averaged monthly, then annually · ${data.pointRetrievalInfo.observationCount ?? "—"} valid annual composites${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} s` : ""}.`)
          : (isTurkish
            ? `Nokta veri alma yedeği: 3 yıllık aylık bloklar · ${data.pointRetrievalInfo.requestCount ?? "—"} Earth Engine isteği${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} sn` : ""}.`
            : `Point retrieval fallback: monthly composites in 3-year blocks · ${data.pointRetrievalInfo.requestCount ?? "—"} Earth Engine requests${data.pointRetrievalInfo.elapsedSeconds != null ? ` · ${data.pointRetrievalInfo.elapsedSeconds} s` : ""}.`)}
        {data.pointRetrievalInfo.fallbackReason && <details className="analysisErrorDetail">
          <summary>{isTurkish ? "İlk sorgu başarısız oldu; yedek analiz tamamlandı · ayrıntı" : "Initial query failed; fallback analysis completed · details"}</summary>
          <small>{String(data.pointRetrievalInfo.fallbackReason).toLowerCase().includes("memory limit exceeded")
            ? (isTurkish
              ? "İlk Earth Engine sorgusu bellek sınırını aştı. Sonuç, yukarıda belirtilen yedek veri alma yöntemiyle tamamlandı. Bu yöntem örnekleme kullanıyorsa sonuç tam poligon alan ortalaması değildir."
              : "The initial Earth Engine query exceeded its memory limit. The result was completed with the fallback retrieval method described above. If that method uses sampling, the result is not a full polygon area mean.")
            : data.pointRetrievalInfo.fallbackReason}</small>
        </details>}
      </div>}
      {data.retrievalMethod === "server_monthly_composites_single_response" && <div className="coverageNote" role="status">
        {isTurkish
          ? `SMAP hızlı tahmini: 3 saatlik görüntüler GEE sunucusunda aylık ortalamaya, ardından yıllık ortalamaya indirgenir · ${data.earthEngineRequestCount ?? "—"} analiz isteği · ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16} nokta.`
          : `SMAP fast estimate: 3-hourly images are averaged monthly, then annually on the GEE server · ${data.earthEngineRequestCount ?? "—"} analysis request(s) · ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16} points.`}
      </div>}
      {data.regionMode && data.retrievalMethod === "monthly_means_sequential_single_year_requests" && <div className="coverageNote" role="status">
        {isTurkish
          ? `MERRA-2 hızlı tahmini: yıllar sırayla, her istekte tek yılın 12 aylık ortalaması · ${data.earthEngineRequestCount ?? "—"} Earth Engine isteği · ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16} nokta.`
          : `MERRA-2 fast estimate: sequential years, each request reduces one year's 12 monthly means · ${data.earthEngineRequestCount ?? "—"} Earth Engine requests · ${data.regionSampleCount ?? 0}/${data.requestedSampleCount ?? 16} points.`}
      </div>}
      {data.sourceWarning && <div className="dataQualityAlert" role="status">
        <strong>{isTurkish ? "VERİ KAYNAĞI NOTU" : "DATA SOURCE NOTE"}</strong>
        <p>{data.sourceWarning}</p>
      </div>}
      {variable === "Sea Level" && <small className="coverageNote">
        {isTurkish ? `Deniz seviyesi konumu: ${name}` : `Sea-level location: ${name}`}
      </small>}
      {repeatedValuePairs.length > 0 && <div className="dataQualityAlert" role="status">
        <strong>{isTurkish ? `AYNI YILLIK DEĞERLER: ${repeatedValuePairs.join(", ")}` : `REPEATED ANNUAL VALUES: ${repeatedValuePairs.join(", ")}`}</strong>
        <p>{isTurkish
          ? `Bu yılların yıllık özetleri kaynak veride sayısal olarak aynı. Uygulama eksik yılları önceki değeri kopyalayarak doldurmaz. ${variable} verisi ${temporalResolution || "kaynağın zaman çözünürlüğünde"} gözlemlerden yıllık ${data.aggregationLabel || "özet"} olarak hesaplanır; aynı sonuç, yıllık agregalar gerçekten eşitse veya poligon kaynak hücresinden küçük olduğu için tek hücre kullanılıyorsa görülebilir. Bu, kendi başına anlamlı trend kanıtı değildir.`
          : `The source-derived annual summaries for these years are numerically identical. The app does not fill missing years by copying the previous value. ${variable} is reduced from ${temporalResolution || "the source cadence"} observations to an annual ${data.aggregationLabel || "summary"}; equal values can occur when annual aggregates match or when a sub-cell polygon uses one source cell. This alone is not evidence of a significant trend.`}</p>
      </div>}
      {data.errorMessage && <small className="coverageNote" role="status">{data.errorMessage}</small>}
      {(data.errorDetail || (!data.errorMessage && stats?.message)) && <details className="analysisErrorDetail">
        <summary>{isTurkish ? "Teknik ayrıntı" : "Technical details"}</summary>
        <small>{data.errorDetail || stats.message}</small>
      </details>}
      {data.failedYears?.length > 0 && <small className="coverageNote" role="status">
        {isTurkish
          ? `Bazı yıllar alınamadı (${data.failedYears.map((item) => item.year).join(", ")}); diğer geçerli yıllar korunmuştur.`
          : `Some years could not be retrieved (${data.failedYears.map((item) => item.year).join(", ")}); other valid years were retained.`}
      </small>}
      {data.failedSampleCount > 0 && <small className="coverageNote" role="status">
        {isTurkish
          ? `${data.failedSampleCount} örnek nokta başarısız oldu; kalan ${data.regionSampleCount} nokta kullanıldı.`
          : `${data.failedSampleCount} sample points failed; the remaining ${data.regionSampleCount} points were used.`}
      </small>}

      {observationSeries
        ? <ObservationSeriesChart
          series={reportSeries}
          unit={unit || ""}
          language={language}
          trendlineStartValue={stats?.trendlineStartValue}
          trendlineEndValue={stats?.trendlineEndValue}
        />
        : <AnnualSeriesChart
          series={reportSeries}
          slope={stats?.slope}
          unit={unit || ""}
          language={language}
        />}

      <div className="questionLabel">
        {isTurkish ? "NE DEĞİŞİYOR?" : "WHAT IS CHANGING?"}
      </div>

      <div className="resultMain">
        {trendText || (isTurkish ? "Sonuç yok" : "No result")}
      </div>

      <div className="analysisGrid">

        {observationSeries ? <>
          <div className="infoCard">
            <span>{isTurkish ? "Son gözlenen su yüzeyi yüksekliği" : "Latest observed water-surface elevation"}</span>
            <strong>{reportSeries.length
              ? `${new Intl.NumberFormat(isTurkish ? "tr-TR" : "en-US", { maximumFractionDigits: 3 }).format(reportSeries[reportSeries.length - 1].value)} ${unit}`
              : "—"}</strong>
          </div>
          <div className="infoCard">
            <span>{isTurkish ? "Betimleyici Sen eğimi" : "Descriptive Sen slope"}</span>
            <strong>
              {stats?.slope != null && Number.isFinite(Number(stats.slope))
                ? `${new Intl.NumberFormat(isTurkish ? "tr-TR" : "en-US", { maximumFractionDigits: 4 }).format(stats.slope)} m/${isTurkish ? "yıl" : "yr"}`
                : "—"}
            </strong>
          </div>
          <div className="infoCard">
            <span>{isTurkish ? "Geçerli uydu geçişi" : "Valid satellite overpasses"}</span>
            <strong>{reportSeries.length}</strong>
          </div>
          <div className="infoCard">
            <span>{isTurkish ? "Son gözlem tarihi" : "Latest observation date"}</span>
            <strong>{formatObservationDate(data.observedEndDate, language)}</strong>
          </div>
        </> : <>
          <div className="infoCard">
            <span>{isTurkish ? "Sen eğimi" : "Sen's slope"}</span>
            <strong>{stats?.slope ?? "—"} /yr</strong>
          </div>
          {!modelOutput && <>
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
          </>}
        </>}

      </div>

      {stats?.testMethod && <small className="coverageNote">
        {isTurkish ? "Mann–Kendall yöntemi: " : "Mann–Kendall method: "}
        {stats.testMethod === "mann_kendall_classic"
          ? (isTurkish ? "klasik test (Hamed–Rao geçersiz sonuç verdi)" : "classic test (Hamed–Rao returned an invalid result)")
          : stats.testMethod === "constant_series_exact"
            ? (isTurkish ? "sabit seri için kesin sonuç" : "exact result for a constant series")
            : (isTurkish ? "Hamed–Rao düzeltmeli test" : "Hamed–Rao modified test")}
      </small>}

      {!modelOutput && <>
      <div className="significanceBox">

        <span>
          {isTurkish ? "İSTATİSTİKSEL ANLAMLILIK" : "STATISTICAL SIGNIFICANCE"}
        </span>

        <strong>
          {observationSeries
            ? (isTurkish ? "UYGULANMADI" : "NOT APPLIED")
            : !hasStatistics
            ? stats?.testStatus === "unavailable"
              ? (isTurkish ? "TEST HESAPLANAMADI" : "TEST UNAVAILABLE")
              : (isTurkish ? "YETERSİZ VERİ" : "INSUFFICIENT DATA")
            : (stats?.significant ?? pValue < 0.05)
            ? (isTurkish ? "ANLAMLI" : "SIGNIFICANT")
            : (isTurkish ? "ANLAMSIZ" : "NOT SIGNIFICANT")}
        </strong>

        <small>
          {observationSeries
            ? isTurkish ? "Düzensiz uydu kaydı; p-değeri raporlanmaz." : "Irregular satellite record; no p-value is reported."
            : isTurkish ? "Eşik: p < 0.05" : "Threshold: p < 0.05"}
        </small>

      </div>

      <div className={`confidenceCard ${localizedConfidence.tone}`}>
        <div className="confidenceTop"><span>{isTurkish ? "İSTATİSTİKSEL KANIT DÜZEYİ" : "STRENGTH OF STATISTICAL EVIDENCE"}</span><strong>{localizedConfidence.label}</strong></div>
        <div className={`confidenceScale ${localizedConfidence.tone}`} aria-label={localizedConfidence.label}><span /><span /><span /></div>
        <small>{localizedConfidence.note}</small>
      </div>
      </>}

      <div className="scienceNote">

          <strong>{isTurkish ? "Yöntem" : "Method"}</strong>

        <p>
          {observationSeries
            ? (isTurkish
              ? "Betimleyici Sen eğimi, düzensiz gözlem tarihleri arasındaki yıllık medyan ikili eğimdir; grafikteki kesikli çizgi bu eğimi özetler. Bu keşifsel özet kalite/buz bayraklarına göre filtrelenmemiş gözlemleri kullanır; p-değeri, Mann–Kendall testi veya istatistiksel anlamlılık iddiası değildir. SWOT değeri seçilen göl özelliğinin su yüzeyi yüksekliğidir; nokta koordinatının ölçümü veya doğrudan su hacmi/debisi değildir."
              : "The descriptive Sen slope is the median pairwise annual slope across irregular observation dates; the dashed chart line summarizes it. This exploratory summary uses observations without quality/ice-flag filtering; it is not a p-value, Mann–Kendall test, or claim of statistical significance. SWOT values describe the selected lake feature's water-surface elevation, not the clicked coordinate or a direct estimate of water volume/discharge.")
            : modelOutput
            ? (isTurkish
              ? "Bu HYCOM model çıktısıdır. Model sürüm geçişleri basamaklı değişimler yaratabileceğinden istatistiksel anlamlılık raporlanmaz; yalnız eğim ve kaynak uyarısı gösterilir."
              : "This is HYCOM model output. Model-version transitions can create step changes, so statistical significance is not reported; only the slope and source warning are shown.")
            : isTurkish
              ? `${stats?.testMethod === "mann_kendall_classic" ? "Klasik Mann–Kendall testi" : "Hamed–Rao düzeltmeli Mann–Kendall testi"} monoton trend kanıtını değerlendirir; Sen eğimi değişim hızını ölçer. ${mapLayerTitle ? `Haritadaki ${mapLayerTitle} renkleri seçili görüntü değerlerini gösterir; tek başına zaman içindeki değişimi veya anlamlı trendi kanıtlamaz.` : ""} Analiz, seçili değişkenin yıllık serisine uygulanır.`
              : `The ${stats?.testMethod === "mann_kendall_classic" ? "classic Mann–Kendall test" : "Hamed–Rao modified Mann–Kendall test"} evaluates evidence for a monotonic trend; Sen's slope estimates its rate. ${mapLayerTitle ? `Map colors in ${mapLayerTitle} show selected image values; they do not by themselves establish change over time or a significant trend.` : ""} The test uses the selected variable's annual series.`}
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
