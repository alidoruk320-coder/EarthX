import { useEffect, useRef, useState } from "react";
import EarthViewer from "../cesium/Viewer";
import SearchBar from "../components/SearchBar";
import AnalysisPanel from "../components/AnalysisPanel";
import YearSlider from "../components/YearSlider";
import { getNasaPowerSeries, NASA_POWER_SERIES } from "../nasa/power";
import { analyzePointGEE, analyzeRegionGEE, analyzeSeaLevel, analyzeSeries, getCascadeCorrelation, getChangeTileUrl, getImpactExposure, GEE_BACKED_LABELS, NASA_POWER_LABELS, LABEL_TO_ID } from "../services/geeApi";
import { fetchGibsCatalog, GIBS_GALLERY_KEYS, GIBS_LAYERS, registerGibsLayer } from "../nasa/earthdata";
import { getBiodiversityContext } from "../services/biodiversity";
import { ANALYSIS_VARIABLES, ANALYSIS_VARIABLE_LABELS, getAnalysisPeriod } from "../data/analysisVariables";

const VARIABLES = ANALYSIS_VARIABLE_LABELS;

function latestCompleteYearForAnalysis(variable) {
  return ANALYSIS_VARIABLES[variable]?.endYear ?? new Date().getUTCFullYear() - 1;
}

const GIBS_ICONS = {
  trueColor: ["◉", "green"],
  ndvi: ["+", "green"],
  landSurfaceTemp: ["°", "hot"],
  snowCover: ["❄", "water"],
  seaSurfaceTemp: ["≈", "water"],
  chlorophyll: ["●", "green"],
  precipitation: ["≋", "rain"],
};

const LAYER_GALLERY = [
  ...GIBS_GALLERY_KEYS.map((key) => ({
    icon: GIBS_ICONS[key][0],
    label: key,
    color: GIBS_ICONS[key][1],
    kind: "gibs",
  })),
  { icon: "↗", label: "Trend Layer", color: "trend" },
  { icon: "♧", label: "Biodiversity Context", color: "biodiversity", kind: "context" },
  { icon: "⇄", label: "Cascade Mode", color: "cascade" },
  { icon: "◎", label: "Impact Mode", color: "impact" },
  { icon: "⌖", label: "Draw Mode", color: "draw" },
  { icon: "◉", label: "Global Story", color: "story" },
];

const GIBS_LABELS = {
  trueColor: "True Color · MODIS Terra",
  ndvi: "Vegetation Index · MODIS Terra",
  landSurfaceTemp: "Land Surface Temperature",
  snowCover: "Snow Cover · Monthly Average",
  seaSurfaceTemp: "Sea Surface Temperature · MUR",
  chlorophyll: "Chlorophyll-a · MODIS Aqua",
  precipitation: "Precipitation Rate · IMERG",
};

const DISCOVERIES = [
  { id: "aral", title: "Aral Sea region", detail: "SMAP soil-moisture change; not a measure of the lake's water level", lat: 45.2, lon: 59.6, variable: "Soil Moisture" },
  { id: "sahel", title: "Sahel Greening Anomaly", detail: "Unexpected vegetation recovery", lat: 14.5, lon: 1.5, variable: "NDVI / Vegetation" },
  { id: "antarctic", title: "Antarctic coastal water-mass anomaly", detail: "GRACE total-water-storage anomaly; not a direct ice-loss measurement", lat: -76, lon: -105, variable: "GRACE Total Water Storage Anomaly" },
];

export default function Earth({ language = "en", setLanguage, onOpenStory }) {
  const viewerRef = useRef(null);
  const analysisRequestRef = useRef(0);
  const biodiversityRequestRef = useRef(0);
  const isTurkish = language === "tr";
  const copy = isTurkish ? {
    subtitle: "DÜNYA VERİSİ ZAMAN AYNASI",
    gallery: "NASA GIBS + BİYOÇEŞİTLİLİK",
    lens: "BİR MERCEK SEÇ",
    discoveries: "ANLIK KEŞİFLER",
    story: "HİKAYE",
    legend: "DÜNYA SİSTEMİ TRENDİ",
    increasing: "Artıyor",
    decreasing: "Azalıyor",
    neutral: "Anlamsız",
    challenge: ["NE?", "NEREDE?", "NE KADAR?", "ANLAMLI MI?"],
    draw: "NOKTA MODU",
    explain: "Açıklama",
    close: "Kapat",
    source: "Veri kaynağı",
  } : {
    subtitle: "EARTH DATA TIME MIRROR",
    gallery: "NASA GIBS + BIODIVERSITY",
    lens: "SELECT A LENS",
    discoveries: "INSTANT DISCOVERIES",
    story: "STORY",
    legend: "EARTH SYSTEM TREND",
    increasing: "Increasing",
    decreasing: "Decreasing",
    neutral: "Not significant",
    challenge: ["WHAT?", "WHERE?", "HOW MUCH?", "IS IT SIGNIFICANT?"],
    draw: "DRAW MODE",
    explain: "Mode guide",
    close: "Close",
    source: "Data source",
  };
  const translatedLabels = {
    Temperature: "Sıcaklık",
    Precipitation: "Yağış",
    "NDVI / Vegetation": "NDVI / Bitki Örtüsü",
    "Soil Moisture": "Toprak Nemi",
    "GRACE Total Water Storage Anomaly": "GRACE Toplam Kara Su Depolama Anomalisi",
    "GPM Precipitation Rate": "GPM Yağış Hızı",
    "Total Column Ozone": "Toplam Sütun Ozonu",
    "MERRA-2 Air Temperature": "MERRA-2 Hava Sıcaklığı",
    "MERRA-2 Precipitable Water": "MERRA-2 Çökelebilir Su Buharı",
    "MERRA-2 Evaporation Rate": "MERRA-2 Buharlaşma Hızı",
    "GLDAS Root-Zone Soil Moisture": "GLDAS Kök Bölgesi Toprak Nemi",
    "GLDAS Surface Runoff": "GLDAS Yüzey Akışı",
    "Sea Level": "Deniz Seviyesi",
    "Biodiversity Context": "Biyoçeşitlilik Bağlamı",
    "Trend Layer": "Trend Katmanı",
    "Cascade Mode": "Cascade Modu",
    "Impact Mode": "Etki Modu",
    "Global Story": "Küresel Hikâye",
  };
  const translatedGibsLabels = {
    trueColor: "Gerçek Renk · MODIS Terra",
    ndvi: "Bitki Örtüsü İndeksi · MODIS Terra",
    landSurfaceTemp: "Arazi Yüzey Sıcaklığı",
    snowCover: "Kar Örtüsü · Aylık Ortalama",
    seaSurfaceTemp: "Deniz Yüzeyi Sıcaklığı · MUR",
    chlorophyll: "Klorofil-a · MODIS Aqua",
    precipitation: "Yağış Hızı · IMERG",
  };
  const displayLabel = (label) => isTurkish
    ? translatedLabels[label] || translatedGibsLabels[label] || label
    : GIBS_LABELS[label] || label;
  const discoveryTranslations = {
    aral: { title: "Aral Gölü çevresi", detail: "SMAP toprak nemi değişimi; göl seviyesi ölçümü değildir" },
    sahel: { title: "Sahel'de Beklenmedik Yeşillenme", detail: "Kurak bölgede bitki örtüsü artışı" },
    antarctic: { title: "Antarktika çevresi su kütlesi", detail: "GRACE toplam su depolama anomalisi; buz kaybının doğrudan ölçümü değildir" },
  };
  const discoveryCopy = (discovery) => isTurkish ? discoveryTranslations[discovery.id] : discovery;

  const [year, setYear] = useState(2026);
  const [selectedMapLayer, setSelectedMapLayer] = useState("trueColor");
  const [mode, setMode] = useState("trend");
  const [selectedVariable, setSelectedVariable] =
    useState("NDVI / Vegetation");
  const [regionAnalysisMode, setRegionAnalysisMode] = useState("sampled_boundary_filtered");

  const [analysis, setAnalysis] = useState(null);
  const [biodiversityContext, setBiodiversityContext] = useState(null);
  const [selectedPlace, setSelectedPlace] = useState(null);

  const [discoveriesOpen, setDiscoveriesOpen] = useState(true);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [catalogLayers, setCatalogLayers] = useState([]);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [changeLayerEnabled, setChangeLayerEnabled] = useState(false);
  const [changeLayerLoading, setChangeLayerLoading] = useState(false);
  const [changeLayerError, setChangeLayerError] = useState("");
  const [activeChangePeriod, setActiveChangePeriod] = useState(null);
  const [layerRangeNotice, setLayerRangeNotice] = useState("");
  const [drawMode, setDrawMode] = useState(false);
  const [modeGuide, setModeGuide] = useState(null);
  const [impactResult, setImpactResult] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState("");
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [cascadeVariable, setCascadeVariable] = useState("NDVI / Vegetation");
  const [cascadeResult, setCascadeResult] = useState(null);
  const [cascadeLoading, setCascadeLoading] = useState(false);
  const [layerDataStatus, setLayerDataStatus] = useState({
    status: "loading",
    variable: "NDVI / Vegetation",
    year: 2026,
  });
  const mapLayer = GIBS_LAYERS[selectedMapLayer];
  const minYear = mapLayer.minYear;
  const maxYear = mapLayer.maxYear;
  const selectedLayerTitle = mapLayer.title || selectedMapLayer;

  function getTrendMapSource(variable) {
    if (variable === "Temperature") return "NASA MODIS Terra LST · MODIS/061/MOD11A2 (LST_Day_1km)";
    if (variable === "Precipitation") return "NASA GPM IMERG monthly rate · NASA/GPM_L3/IMERG_MONTHLY_V07 (precipitation)";
    return ANALYSIS_VARIABLES[variable]?.datasetId || ANALYSIS_VARIABLES[variable]?.source || "NASA data product";
  }

  async function openCatalog() {
    setCatalogOpen(true);
    if (catalogLayers.length || catalogLoading) return;
    setCatalogLoading(true);
    setCatalogError("");
    try {
      setCatalogLayers(await fetchGibsCatalog());
    } catch (error) {
      setCatalogError(error.message);
    } finally {
      setCatalogLoading(false);
    }
  }

  function updateWorld(nextYear, nextLayer = selectedMapLayer) {
    viewerRef.current?.setGibsLayer(nextLayer, nextYear);
  }

  async function loadBiodiversityContext(lat, lon) {
    const requestId = ++biodiversityRequestRef.current;
    setBiodiversityContext({ status: "loading" });
    try {
      const result = await getBiodiversityContext(Number(lat), Number(lon), 50);
      if (requestId !== biodiversityRequestRef.current) return;
      setBiodiversityContext({ status: "ready", ...result });
    } catch (error) {
      console.error(error);
      if (requestId !== biodiversityRequestRef.current) return;
      setBiodiversityContext({
        status: "error",
        message: isTurkish
          ? "Biyoçeşitlilik bağlamı şu anda alınamadı. Lütfen daha sonra tekrar deneyin."
          : "Biodiversity context is temporarily unavailable. Please try again later.",
      });
    }
  }

  function getRegionBounds(place) {
    if (!place || !Array.isArray(place.boundingbox) || place.boundingbox.length < 4) return null;
    const south = Number(place.boundingbox[0]);
    const north = Number(place.boundingbox[1]);
    const west = Number(place.boundingbox[2]);
    const east = Number(place.boundingbox[3]);
    if (![south, north, west, east].every((value) => Number.isFinite(value))) return null;
    return { south, north, west, east };
  }

  function polygonToCoordinates(geojson) {
    if (!geojson) return [];
    const parsed = typeof geojson === "string" ? JSON.parse(geojson) : geojson;
    const geometry = parsed?.type === "FeatureCollection"
      ? parsed.features?.[0]?.geometry
      : parsed?.type === "Feature"
        ? parsed.geometry
        : parsed;
    if (!geometry) return [];
    if (geometry.type === "Polygon") return [geometry.coordinates];
    if (geometry.type === "MultiPolygon") return geometry.coordinates;
    return [];
  }

  function pointInPolygon(lat, lon, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const xi = polygon[i][0];
      const yi = polygon[i][1];
      const xj = polygon[j][0];
      const yj = polygon[j][1];
      const intersects = ((yi > lat) !== (yj > lat))
        && (lon < ((xj - xi) * (lat - yi)) / (yj - yi + Number.EPSILON) + xi);
      if (intersects) inside = !inside;
    }
    return inside;
  }

  function getRegionSamplePoints(place, sampleCount = 4) {
    const bounds = getRegionBounds(place);
    if (!bounds) return [];

    const polygons = polygonToCoordinates(place?.geojson);
    if (!polygons.length) return [];
    const gridSize = Math.max(2, sampleCount);
    const latValues = Array.from({ length: gridSize }, (_, index) => {
      const ratio = (index + 0.5) / gridSize;
      return bounds.south + (bounds.north - bounds.south) * ratio;
    });
    const lonValues = Array.from({ length: gridSize }, (_, index) => {
      const ratio = (index + 0.5) / gridSize;
      return bounds.west + (bounds.east - bounds.west) * ratio;
    });

    const points = [];
    for (const lat of latValues) {
      for (const lon of lonValues) {
        const withinPolygon = polygons.some((rings) =>
          pointInPolygon(lat, lon, rings[0]) && !rings.slice(1).some((hole) => pointInPolygon(lat, lon, hole))
        );
        if (!withinPolygon) continue;
        const weight = Math.cos((lat * Math.PI) / 180);
        points.push({ lat, lon, weight });
      }
    }

    return points;
  }

  async function runImpactAnalysis() {
    const bounds = getRegionBounds(selectedPlace);
    if (!bounds) {
      setImpactError(isTurkish
        ? "Etki analizi için önce sınırı olan bir ülke veya bölge arayın."
        : "Search for a country or region with a boundary before running exposure analysis.");
      setImpactResult(null);
      return;
    }
    setImpactLoading(true);
    setImpactError("");
    setImpactResult(null);
    try {
      const result = await getImpactExposure(bounds);
      setImpactResult(result);
    } catch (error) {
      setImpactError(error.message || (isTurkish ? "Bölgesel maruziyet analizi alınamadı." : "Regional exposure analysis could not be loaded."));
    } finally {
      setImpactLoading(false);
    }
  }

  function mergeSeriesForRegion(pointSeriesList, pointWeights = null) {
    const byYear = new Map();
    pointSeriesList.forEach((series, index) => {
      const weight = pointWeights?.[index]?.weight ?? 1;
      series.forEach((point) => {
        const year = Number(point.year);
        if (!Number.isFinite(year)) return;
        const existing = byYear.get(year) ?? { totalWeight: 0, weightedSum: 0 };
        existing.totalWeight += weight;
        existing.weightedSum += Number(point.value) * weight;
        byYear.set(year, existing);
      });
    });

    return Array.from(byYear.entries())
      .map(([year, aggregate]) => ({
        year: Number(year),
        value: aggregate.totalWeight > 0 ? aggregate.weightedSum / aggregate.totalWeight : 0,
      }))
      .sort((a, b) => a.year - b.year);
  }

  async function runAnalysis(placeName, variable, selectedYear, lat, lon, place = null, requestedRegionMode = regionAnalysisMode) {
    const requestId = ++analysisRequestRef.current;
    const completeDataEndYear = Math.min(Number(selectedYear), latestCompleteYearForAnalysis(variable));
    const [dataStartYear] = getAnalysisPeriod(variable);
    setAnalysisLoading(true);
    setAnalysis(null);
    try {
      const regionBounds = getRegionBounds(place);
      const regionSamplePoints = place ? getRegionSamplePoints(place, 4) : [];
      const regionMode = Boolean(regionBounds && (
        regionSamplePoints.length > 0
        || (requestedRegionMode === "polygon_area_weighted" && place?.geojson && GEE_BACKED_LABELS.includes(variable))
      ));
      const polygonMode = regionMode
        && requestedRegionMode === "polygon_area_weighted"
        && GEE_BACKED_LABELS.includes(variable)
        && Boolean(place?.geojson);
      if (regionBounds && place?.geojson && requestedRegionMode === "sampled_boundary_filtered"
        && regionSamplePoints.length === 0) {
        throw new Error(isTurkish
          ? "Hızlı tahmin için sınır içinde örnek nokta üretilemedi. Poligon analizini seçin."
          : "No sample point fell inside the boundary. Choose polygon analysis for this region.");
      }
      const centerLat = regionBounds ? (regionBounds.south + regionBounds.north) / 2 : Number(lat);
      const centerLon = regionBounds ? (regionBounds.west + regionBounds.east) / 2 : Number(lon);
      const regionMethodNote = regionMode
        ? polygonMode
          ? (isTurkish
            ? "Poligon sonucu, her yılın geçerli GEE piksellerinin alanlarıyla ağırlıklandırılmış ortalamasıdır."
            : "Polygon result is the area-weighted mean of valid GEE pixels for each year.")
          : isTurkish
          ? "Bölgesel sonuç, ülke/bölge sınırı içinde seçilmiş örnek noktaların ağırlıklı ortalamasıdır; bu hâlâ tam alan-ağırlıklı poligon agregasyonu değildir, yalnızca daha güvenilir bir bölge tahminidir."
          : "The regional result is a weighted mean of boundary-filtered sample points; this is still an approximate region estimate, not a full area-weighted polygon aggregation."
        : null;

      let series;
      let stats;
      let source;
      let datasetId;
      let unit;
      let regionResponse = null;

      if (completeDataEndYear < dataStartYear) {
        series = [];
        source = ANALYSIS_VARIABLES[variable]?.source || "NASA data source";
        datasetId = ANALYSIS_VARIABLES[variable]?.datasetId;
        unit = ANALYSIS_VARIABLES[variable]?.unit;
        stats = { trend: "Insufficient Data", slope: null, zScore: null, pValue: null, significant: false };
      } else if (polygonMode) {
        regionResponse = await analyzeRegionGEE(place.geojson, variable, dataStartYear, completeDataEndYear);
        series = (regionResponse.raw_series || []).map((point) => ({
          year: Number(point.year),
          value: Number(point.value),
        }));
        source = regionResponse.source || ANALYSIS_VARIABLES[variable]?.source || "Google Earth Engine";
        datasetId = regionResponse.dataset_id || ANALYSIS_VARIABLES[variable]?.datasetId;
        unit = regionResponse.unit || ANALYSIS_VARIABLES[variable]?.unit;
        stats = {
          trend: regionResponse.trend,
          slope: regionResponse.sen_slope,
          zScore: regionResponse.z_score,
          pValue: regionResponse.p_value,
          significant: regionResponse.significant,
          message: regionResponse.message,
        };
      } else if (NASA_POWER_LABELS.includes(variable)) {
        let pointSeries;
        if (regionMode) {
          pointSeries = await Promise.all(
            regionSamplePoints.map((point) => getNasaPowerSeries(point.lat, point.lon, variable, dataStartYear, completeDataEndYear))
          );
          series = mergeSeriesForRegion(pointSeries, regionSamplePoints);
        } else {
          series = await getNasaPowerSeries(Number(lat), Number(lon), variable, dataStartYear, completeDataEndYear);
        }
        source = ANALYSIS_VARIABLES[variable]?.source || "NASA POWER";
        datasetId = ANALYSIS_VARIABLES[variable]?.datasetId || `NASA POWER daily parameter ${NASA_POWER_SERIES[variable]?.parameter || "unknown"}`;
        unit = ANALYSIS_VARIABLES[variable]?.unit || NASA_POWER_SERIES[variable]?.unit;
        const calculated = series.length >= 8
          ? await analyzeSeries(series, variable, unit, datasetId, dataStartYear, completeDataEndYear)
          : null;
        stats = calculated ? { trend: calculated.trend, slope: calculated.sen_slope, zScore: calculated.z_score, pValue: calculated.p_value, significant: calculated.significant, message: calculated.message } : { trend: "Insufficient Data", slope: null, zScore: null, pValue: null, significant: false };
      } else if (GEE_BACKED_LABELS.includes(variable)) {
        let pointResults;
        if (regionMode) {
          pointResults = await Promise.all(
            regionSamplePoints.map((point) => analyzePointGEE(point.lat, point.lon, variable, dataStartYear, completeDataEndYear))
          );
        } else {
          pointResults = [await analyzePointGEE(Number(lat), Number(lon), variable, dataStartYear, completeDataEndYear)];
        }
        const normalisedSeries = pointResults
          .map((result) => (result.raw_series || []).map((point) => ({
            year: Number(point.year || point.date?.slice(0, 4)),
            value: Number(point.value),
          })))
          .filter((values) => values.length > 0);

        series = regionMode
          ? mergeSeriesForRegion(normalisedSeries, regionSamplePoints)
          : mergeSeriesForRegion(normalisedSeries, [{ weight: 1 }]);
        const result = pointResults[0] || {};
        datasetId = ANALYSIS_VARIABLES[variable]?.datasetId || result.dataset_id;
        source = ANALYSIS_VARIABLES[variable]?.source || "Google Earth Engine";
        unit = result.unit || ANALYSIS_VARIABLES[variable]?.unit;
        const calculated = series.length >= 8
          ? await analyzeSeries(series, variable, unit, datasetId, dataStartYear, completeDataEndYear)
          : null;
        stats = calculated ? { trend: calculated.trend, slope: calculated.sen_slope, zScore: calculated.z_score, pValue: calculated.p_value, significant: calculated.significant, message: calculated.message } : { trend: "Insufficient Data", slope: null, zScore: null, pValue: null, significant: false };
      } else if (variable === "Sea Level") {
        if (regionMode) {
          const sampled = await Promise.allSettled(regionSamplePoints.map((point) =>
            analyzeSeaLevel(point.lat, point.lon, 1993, completeDataEndYear)));
          const valid = sampled.flatMap((result, index) => result.status === "fulfilled"
            ? [{ result: result.value, point: regionSamplePoints[index] }]
            : []);
          if (!valid.length) throw new Error(isTurkish
            ? "Sınır içindeki örnek noktalarda okyanus deniz seviyesi hücresi bulunamadı."
            : "No ocean sea-level cells were found at the sampled boundary points.");
          series = mergeSeriesForRegion(valid.map(({ result }) => result.raw_series || []), valid.map(({ point }) => point));
          source = valid[0].result.source;
          datasetId = valid[0].result.dataset_id;
          unit = valid[0].result.unit;
          const calculated = series.length >= 8
            ? await analyzeSeries(series, variable, unit, datasetId, 1993, completeDataEndYear)
            : null;
          stats = calculated
            ? { trend: calculated.trend, slope: calculated.sen_slope, zScore: calculated.z_score, pValue: calculated.p_value, significant: calculated.significant, message: calculated.message }
            : { trend: "Insufficient Data", slope: null, zScore: null, pValue: null, significant: false };
          regionResponse = { method: "sampled_boundary_filtered", sample_count: valid.length };
        } else {
          const seaLevel = await analyzeSeaLevel(Number(lat), Number(lon), 1993, completeDataEndYear);
          series = seaLevel.raw_series || [];
          source = seaLevel.source;
          datasetId = seaLevel.dataset_id;
          unit = seaLevel.unit;
          stats = { trend: seaLevel.trend, slope: seaLevel.sen_slope, zScore: seaLevel.z_score, pValue: seaLevel.p_value, significant: seaLevel.significant, message: seaLevel.message };
        }
      } else {
        throw new Error(`No analysis provider configured for ${variable}`);
      }

      if (requestId !== analysisRequestRef.current) return;
      if (regionMode && !regionResponse) {
        regionResponse = { method: "sampled_boundary_filtered", sample_count: regionSamplePoints.length };
      }
      setAnalysis({
        name: regionMode ? `${placeName} (${isTurkish ? "bölgesel ortalama" : "regional average"})` : placeName,
        variable,
        year: selectedYear,
        analysisEndYear: completeDataEndYear,
        lat: Number(centerLat),
        lon: Number(centerLon),
        regionMode,
        regionSampleCount: regionMode ? (regionResponse?.sample_count ?? regionSamplePoints.length) : 0,
        method: regionResponse?.method || (regionMode ? "sampled_boundary_filtered" : "point"),
        validPixelCount: regionResponse?.valid_pixel_count ?? null,
        validPixelCountRange: regionResponse?.valid_pixel_count_range ?? null,
        resolutionWarning: regionResponse?.resolution_warning ?? null,
        lowCoverageYears: regionResponse?.low_coverage_years ?? [],
        missingYears: regionResponse?.missing_years ?? [],
        missingYearWarning: regionResponse?.missing_year_warning ?? null,
        shortSeriesWarning: regionResponse?.short_series_warning ?? null,
        aggregationLabel: regionResponse?.aggregation_label ?? null,
        elapsedSeconds: regionResponse?.elapsed_seconds ?? null,
        regionMethodNote: regionResponse?.method === "polygon_area_weighted_single_cell"
          ? (isTurkish
            ? "Çözünürlük uyarısı: bu sonuç seçilen poligon için merkez hücreye dayanır."
            : "Resolution note: this result uses the center cell for the selected polygon.")
          : regionMethodNote,
        series,
        observedStartYear: series.length ? Math.min(...series.map((point) => point.year)) : null,
        observedEndYear: series.length ? Math.max(...series.map((point) => point.year)) : null,
        source,
        datasetId,
        datasetDocUrl: ANALYSIS_VARIABLES[variable]?.sourceUrl,
        unit,
        stats,
        errorMessage: variable === "Soil Moisture" && series.length === 0 && completeDataEndYear >= dataStartYear
          ? (isTurkish
            ? "Bu koordinatta geçerli SMAP kara pikseli bulunamadı. Toprak nemi deniz yüzeyinde ölçülmez; kıyı veya açık deniz noktaları veri döndürmeyebilir."
            : "No valid SMAP land pixel was found at this coordinate. Soil moisture is not measured over the ocean; coastal or offshore points may have no data.")
          : variable === "Sea Level" && !series.length
            ? (isTurkish
              ? "Bu koordinatta NASA okyanus altimetri ızgarası bulunamadı. Nokta kara içindeyse kıyıdaki bir deniz noktasına tıklayın; bu ürün yerel gelgit ölçeri değildir."
              : "No NASA ocean-altimetry grid is available at this coordinate. If the point is inland, select an ocean point near the coast; this product is not a local tide-gauge record.")
          : null,
        coverageMessage: selectedYear > completeDataEndYear
          ? (isTurkish
            ? `Seçili yıl ${selectedYear}; trend analizinde yalnızca tamamlanmış yıllar kullanılır ve seri ${completeDataEndYear} yılında biter.`
            : `Selected display year: ${selectedYear}; trend analysis uses complete years only and ends at ${completeDataEndYear}.`)
          : completeDataEndYear < dataStartYear
          ? (isTurkish
            ? `${variable} verisi ${dataStartYear} yılında başlar; seçili yıl için zaman serisi oluşturulamaz.`
            : `${variable} data begins in ${dataStartYear}; no time series is available for the selected year.`)
          : null,
      });
    } catch (error) {
      console.error(error);
      if (requestId !== analysisRequestRef.current) return;
      setAnalysis({
        name: placeName,
        variable,
        year: selectedYear,
        lat: Number(lat),
        lon: Number(lon),
        series: [],
        observedStartYear: null,
        observedEndYear: null,
        datasetId: null,
        datasetDocUrl: ANALYSIS_VARIABLES[variable]?.sourceUrl,
        unit: null,
        source: variable === "Sea Level"
          ? "NASA/JPL Sea Level Change Portal unavailable"
          : GEE_BACKED_LABELS.includes(variable) ? "GEE backend unavailable" : "NASA POWER unavailable",
        errorMessage: error.message,
        stats: { trend: "Analysis unavailable", slope: null, zScore: null, pValue: null, significant: false },
      });
    } finally {
      if (requestId === analysisRequestRef.current) setAnalysisLoading(false);
    }
  }

  function handleYearChange(nextYear) {
    setYear(nextYear);
    setLayerRangeNotice("");
    updateWorld(nextYear);

    if (selectedPlace) {
      runAnalysis(
        selectedPlace.display_name,
        selectedVariable,
        nextYear,
        selectedPlace.lat,
        selectedPlace.lon,
        selectedPlace
      );
    }
  }

  function handleVariableChange(event) {
    const variable = event.target.value;
    setSelectedVariable(variable);

    if (selectedPlace) {
      runAnalysis(
        selectedPlace.display_name,
        variable,
        year,
        selectedPlace.lat,
        selectedPlace.lon,
        selectedPlace
      );
    }
  }

  function handleMapLayerSelect(layerKey) {
    const layer = GIBS_LAYERS[layerKey];
    const nextYear = Math.max(layer.minYear, Math.min(year, layer.maxYear));
    if (layer.temporal !== false && nextYear !== year) {
      setLayerRangeNotice(isTurkish
        ? `${layer.title} için kullanılabilir zaman aralığı ${layer.minYear}–${layer.maxYear}. Zaman çizelgesi ${year} yerine ${nextYear} yılına alındı.`
        : `${layer.title} is available from ${layer.minYear} to ${layer.maxYear}. The timeline moved from ${year} to ${nextYear}.`);
    } else {
      setLayerRangeNotice("");
    }
    setSelectedMapLayer(layerKey);
    if (nextYear !== year) setYear(nextYear);
    updateWorld(nextYear, layerKey);
    if (nextYear !== year && selectedPlace) {
      runAnalysis(
        selectedPlace.display_name,
        selectedVariable,
        nextYear,
        selectedPlace.lat,
        selectedPlace.lon,
        selectedPlace
      );
    }
  }

  function handleCatalogLayerSelect(layer) {
    registerGibsLayer(layer);
    handleMapLayerSelect(layer.id);
    setCatalogOpen(false);
  }

  async function toggleChangeLayer() {
    if (changeLayerLoading) return;
    if (changeLayerEnabled) {
      viewerRef.current?.setChangeLayer(null);
      setChangeLayerEnabled(false);
      setActiveChangePeriod(null);
      return;
    }
    const [startYear] = getAnalysisPeriod(selectedVariable);
    const endYear = Math.min(year, latestCompleteYearForAnalysis(selectedVariable));
    if (!LABEL_TO_ID[selectedVariable] || endYear - startYear < 2) {
      setChangeLayerError(isTurkish
        ? "Bu analiz değişkeni veya dönem için değişim haritası kullanılamıyor."
        : "A change map is not available for this variable or period.");
      return;
    }

    setChangeLayerLoading(true);
    setChangeLayerError("");
    try {
      const tileUrl = await getChangeTileUrl(selectedVariable, startYear, endYear);
      if (!tileUrl) throw new Error(isTurkish ? "Değişim haritası için karo adresi alınamadı." : "No change-map tile URL was returned.");
      viewerRef.current?.setChangeLayer(tileUrl);
      setActiveChangePeriod({ variable: selectedVariable, startYear, endYear });
      setChangeLayerEnabled(true);
    } catch (error) {
      setChangeLayerError(error.message);
    } finally {
      setChangeLayerLoading(false);
    }
  }

  const filteredCatalogLayers = catalogLayers
    .filter((layer) => `${layer.title} ${layer.id} ${layer.abstract}`.toLowerCase().includes(catalogQuery.trim().toLowerCase()))
    .slice(0, 80);

  function handleSearch(place) {
    setSelectedPlace(place);
    loadBiodiversityContext(place.lat, place.lon);

    const boundaryShown = place.geojson
      ? viewerRef.current?.setSearchBoundary(place.geojson)
      : Promise.resolve(false);
    Promise.resolve(boundaryShown).then((shown) => {
      if (!shown) viewerRef.current?.flyTo(Number(place.lat), Number(place.lon));
    });

    runAnalysis(
      place.display_name,
      selectedVariable,
      year,
      Number(place.lat),
      Number(place.lon),
      place
    );
  }

  function handlePointClick(lat, lon) {
    const place = {
      display_name: `Point ${lat.toFixed(3)}°, ${lon.toFixed(3)}°`,
      lat,
      lon,
    };
    setSelectedPlace(place);
    loadBiodiversityContext(lat, lon);
    setDrawMode(false);
    setModeGuide(null);
    viewerRef.current?.flyTo(lat, lon);
    runAnalysis(place.display_name, selectedVariable, year, lat, lon, place);
  }

  function handleDiscovery(discovery) {
    const placeName = discoveryCopy(discovery).title;
    const place = { display_name: placeName, lat: discovery.lat, lon: discovery.lon };
    setDiscoveriesOpen(false);
    setSelectedVariable(discovery.variable);
    setSelectedPlace(place);
    loadBiodiversityContext(discovery.lat, discovery.lon);
    viewerRef.current?.flyTo(discovery.lat, discovery.lon);
    runAnalysis(placeName, discovery.variable, year, discovery.lat, discovery.lon, place);
  }

  function handleGallerySelect(layer) {
    if (layer.kind === "gibs") {
      handleMapLayerSelect(layer.label);
      return;
    }
    if (layer.kind === "context") {
      if (selectedPlace) loadBiodiversityContext(selectedPlace.lat, selectedPlace.lon);
      return;
    }
    if (VARIABLES.includes(layer.label)) {
      handleVariableChange({ target: { value: layer.label } });
      return;
    }
    setDiscoveriesOpen(false);
    if (layer.label === "Cascade Mode" || layer.label === "Trend Layer") setMode("climate");
    if (layer.label === "Trend Layer" && selectedPlace) {
      runAnalysis(selectedPlace.display_name, selectedVariable, year,
        selectedPlace.lat, selectedPlace.lon, selectedPlace);
    }
    if (layer.label === "Cascade Mode") {
      setCascadeResult(null);
      setModeGuide({ type: "cascade" });
    }
    if (layer.label === "Impact Mode") {
      setMode("ai");
      setModeGuide({ type: "impact" });
    }
    if (layer.label === "Draw Mode") {
      setDrawMode(true);
      setModeGuide({ type: "draw" });
    }
    if (layer.label === "Global Story") onOpenStory();
  }

  async function runCascade() {
    if (!selectedPlace || !GEE_BACKED_LABELS.includes(selectedVariable) || !GEE_BACKED_LABELS.includes(cascadeVariable)) return;
    setCascadeLoading(true);
    setCascadeResult(null);
    try {
      const pair = [selectedVariable, cascadeVariable];
      const startYear = Math.max(...pair.map((variable) => getAnalysisPeriod(variable)[0]));
    const endYear = Math.min(year, ...pair.map((variable) => latestCompleteYearForAnalysis(variable)));
    if (endYear - startYear < 9) {
      setCascadeResult(null);
      setCascadeResult({ message: isTurkish
        ? "Gecikmeli korelasyon için ortak dönemde en az 10 yıllık veri gerekir."
        : "Lagged correlation requires at least 10 shared annual observations." });
      setCascadeLoading(false);
      return;
    }
      const result = await getCascadeCorrelation(
        Number(selectedPlace.lat), Number(selectedPlace.lon),
        selectedVariable, cascadeVariable, startYear, endYear
      );
      setCascadeResult(result);
      setAnalysis((current) => current ? { ...current, cascade: result } : current);
    } catch (error) {
      setCascadeResult({ error: error.message });
    } finally {
      setCascadeLoading(false);
    }
  }

  return (
    <div className="earthPage">

      {/* 3D EARTH */}
      <EarthViewer ref={viewerRef} onPointClick={handlePointClick} onLayerStatus={setLayerDataStatus} />

      {/* TOP BRAND */}
      <div className="earthBrand">
        <div className="earthBrandTitle">
          TWIN EARTH
        </div>

        <div className="earthBrandSubtitle">
            {copy.subtitle}
        </div>

        <div className="languageBar earthLanguage" aria-label="Language selector">
          <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
          <button className={language === "tr" ? "active" : ""} onClick={() => setLanguage("tr")}>TR</button>
        </div>
      </div>

      {/* SEARCH */}
      <SearchBar onSearch={handleSearch} language={language} />

      <div className={`layerDataBadge ${layerDataStatus.status}`}>
        {layerDataStatus.status === "live"
          ? (isTurkish
            ? `CANLI NASA GIBS · ${layerDataStatus.layer} · ${layerDataStatus.date || "en güncel görüntü"}`
            : `LIVE NASA GIBS · ${layerDataStatus.layer} · ${layerDataStatus.date || "latest available image"}`)
          : layerDataStatus.status === "partial"
            ? (isTurkish
              ? `NASA GIBS · ${layerDataStatus.layer} · ${layerDataStatus.date || ""} · Bu konum/yakınlaştırmada bazı karoların verisi yok`
              : `NASA GIBS · ${layerDataStatus.layer} · ${layerDataStatus.date || ""} · Some tiles have no data at this location/zoom`)
          : layerDataStatus.status === "loading"
            ? (isTurkish
              ? `NASA GIBS katmanı yükleniyor · ${selectedLayerTitle} · ${year}-07-01`
              : `Loading NASA GIBS layer · ${selectedLayerTitle} · ${year}-07-01`)
            : layerDataStatus.status === "no-data"
              ? (isTurkish
                ? `NASA GIBS verisi yok · ${layerDataStatus.layer || selectedLayerTitle} · ${layerDataStatus.detail || ""}`
                : `No NASA GIBS data · ${layerDataStatus.layer || selectedLayerTitle} · ${layerDataStatus.detail || ""}`)
            : (isTurkish
              ? `NASA GIBS katmanı yüklenemedi · ${layerDataStatus.layer || displayLabel(selectedMapLayer)}${layerDataStatus.detail ? ` · ${layerDataStatus.detail}` : ""}`
              : `NASA GIBS layer unavailable · ${layerDataStatus.layer || displayLabel(selectedMapLayer)}${layerDataStatus.detail ? ` · ${layerDataStatus.detail}` : ""}`)}
      </div>

      <div className="layerGallery">
        <div className="galleryHeading"><span>{copy.gallery}</span><small>{copy.lens}</small></div>
        <button className="fullCatalogButton" onClick={openCatalog}>
          {isTurkish ? "TÜM WORLDVIEW KATMANLARINI ARA" : "SEARCH FULL WORLDVIEW CATALOG"}
        </button>
        <div className="galleryGrid">
          {LAYER_GALLERY.map((layer) => (
            <button
              key={layer.label}
              className={`galleryTile ${layer.color} ${(layer.kind === "gibs" && selectedMapLayer === layer.label) || (layer.kind === "context" && biodiversityContext?.status === "ready") ? "active" : ""}`}
              aria-pressed={layer.kind === "gibs"
                ? selectedMapLayer === layer.label
                : layer.kind === "context"
                  ? biodiversityContext?.status === "ready"
                  : undefined}
              onClick={() => handleGallerySelect(layer)}
            >
              <span className="galleryOrb">{layer.icon}</span><span>{layer.label === "Draw Mode" ? copy.draw : displayLabel(layer.label)}</span>
            </button>
          ))}
        </div>
      </div>

      {catalogOpen && (
        <div className="gibsCatalogBackdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setCatalogOpen(false);
        }}>
          <section className="gibsCatalogDialog" role="dialog" aria-modal="true" aria-labelledby="gibsCatalogTitle">
            <header>
              <div>
                <span>{isTurkish ? "NASA WORLDVIEW / GIBS" : "NASA WORLDVIEW / GIBS"}</span>
                <h2 id="gibsCatalogTitle">{isTurkish ? "Katman kataloğu" : "Layer catalog"}</h2>
              </div>
              <button aria-label={isTurkish ? "Kataloğu kapat" : "Close catalog"} onClick={() => setCatalogOpen(false)}>×</button>
            </header>
            <p>{isTurkish
              ? "NASA'nın WMTS kataloğu isteğe bağlı yüklenir. Listede Cesium haritasıyla uyumlu Web Mercator görüntü katmanları bulunur."
              : "NASA's WMTS catalog loads only when requested. Results are Web Mercator imagery layers compatible with the Cesium map."}</p>
            <input
              type="search"
              value={catalogQuery}
              onChange={(event) => setCatalogQuery(event.target.value)}
              placeholder={isTurkish ? "Katman adı, kimliği veya açıklamasında ara" : "Search layer name, identifier, or description"}
              aria-label={isTurkish ? "GIBS katmanlarında ara" : "Search GIBS layers"}
            />
            <div className="gibsCatalogResults" aria-live="polite">
              {catalogLoading
                ? <p>{isTurkish ? "NASA GIBS kataloğu yükleniyor…" : "Loading NASA GIBS catalog…"}</p>
                : catalogError
                  ? <p className="gibsCatalogError">{catalogError}</p>
                  : filteredCatalogLayers.length
                    ? filteredCatalogLayers.map((layer) => (
                      <button key={layer.id} onClick={() => handleCatalogLayerSelect(layer)}>
                        <strong>{layer.title}</strong>
                        <small>{layer.id} · {layer.temporal ? `${layer.minYear}–${layer.maxYear}` : (isTurkish ? "zamansız" : "static")}</small>
                      </button>
                    ))
                    : <p>{isTurkish ? "Eşleşen uyumlu katman bulunamadı." : "No compatible layers match this search."}</p>}
            </div>
            {!catalogLoading && !catalogError && filteredCatalogLayers.length === 80 && (
              <small className="gibsCatalogLimit">{isTurkish ? "İlk 80 sonuç gösteriliyor; aramanızı daraltın." : "Showing the first 80 results; refine your search."}</small>
            )}
          </section>
        </div>
      )}

      <aside className={`discoveries ${discoveriesOpen ? "open" : ""}`}>
        <button className="discoveriesToggle" onClick={() => setDiscoveriesOpen((value) => !value)}><span>⚡</span> {copy.discoveries} <b>{discoveriesOpen ? "−" : "+"}</b></button>
        {discoveriesOpen && <div className="discoveryList">
          {DISCOVERIES.map((discovery) => (
            <button key={discovery.id} className="discoveryItem" onClick={() => handleDiscovery(discovery)}>
              <strong>{discoveryCopy(discovery).title}</strong><small>{discoveryCopy(discovery).detail}</small><span>{isTurkish ? "İNCELE" : "EXPLORE"} ↗</span>
            </button>
          ))}
        </div>}
      </aside>

      {/* MAIN CONTROLS */}
      <div className="earthControls">
        <label className="analysisVariableControl">
          <span>{isTurkish ? "İSTATİSTİKSEL ANALİZ" : "STATISTICAL ANALYSIS"}</span>
          <select
            value={selectedVariable}
            onChange={handleVariableChange}
            aria-label={isTurkish ? "İstatistik analiz değişkeni" : "Statistical analysis variable"}
          >
            {VARIABLES.map((variable) => (
              <option key={variable} value={variable}>{displayLabel(variable)}</option>
            ))}
          </select>
        </label>

        <button
          className="storyButton"
          onClick={onOpenStory}
        >
          {copy.story}
        </button>

      </div>

      <div className="trendLegend">
        <div className="legendTitle">{isTurkish ? "HARİTA KATMANI" : "MAP LAYER"}</div>
        <div>{selectedLayerTitle} · {mapLayer.temporal === false ? (isTurkish ? "zamansız katman" : "static layer") : `${year}-07-01`}</div>
        <small>
          {isTurkish
            ? "Zaman çizelgesi her yılın aynı tarihini gösterir; nokta istatistikleri seçili analiz değişkeninden hesaplanır."
            : "The timeline shows the same date each year; point statistics use the separately selected analysis variable."}
        </small>
      </div>

      <aside className={`changeModeBox ${changeLayerEnabled ? "active" : ""}`}>
        <button
          className={`changeModeButton ${changeLayerEnabled ? "active" : ""}`}
          onClick={toggleChangeLayer}
          disabled={changeLayerLoading || (!changeLayerEnabled && (!LABEL_TO_ID[selectedVariable] || Math.min(year, latestCompleteYearForAnalysis(selectedVariable)) - getAnalysisPeriod(selectedVariable)[0] < 2))}
          aria-pressed={changeLayerEnabled}
        >
          <span>!</span>
          {changeLayerLoading
            ? (isTurkish ? "HESAPLANIYOR…" : "CALCULATING…")
            : (isTurkish ? "EN ÇOK DEĞİŞEN YERLER" : "MOST CHANGED AREAS")}
          <b>{changeLayerEnabled ? "−" : "+"}</b>
        </button>
        {changeLayerEnabled && activeChangePeriod && (
          <>
            <div className="changeModeNote">
              {displayLabel(activeChangePeriod.variable)} · {activeChangePeriod.startYear}–{activeChangePeriod.endYear}
              <br />
              {isTurkish ? "Eğim haritası ürünü: " : "Trend-map product: "}{getTrendMapSource(activeChangePeriod.variable)}
              <br />
              {(NASA_POWER_LABELS.includes(activeChangePeriod.variable)) && (isTurkish
                ? "Nokta serisi ayrı NASA POWER ölçümüdür; harita ürünüyle aynı değişken tanımı değildir."
                : "Point statistics use a separate NASA POWER series and are not the same product as the map.")}
              <br />
              {isTurkish ? "Harita: yıllık doğrusal eğim; küresel mutlak eğimin en yüksek %5'i. Piksel bazında anlamlılık testi değildir." : "Map: annual linear slope; top 5% of global absolute slopes. This is not a pixel-level significance test."}
            </div>
            <div className="changeModeLegend">
              <span><i className="decline" />{isTurkish ? "Azalış" : "Decline"}</span>
              <span><i className="increase" />{isTurkish ? "Artış" : "Increase"}</span>
            </div>
          </>
        )}
        {changeLayerError && <div className="changeModeError" role="alert">{changeLayerError}</div>}
      </aside>

      {/* CHALLENGE QUESTIONS */}
      <div className="challengeQuestions">
        {copy.challenge.map((item) => <span key={item}>{item}</span>)}
      </div>

      {/* YEAR */}
      <YearSlider
        year={year}
        setYear={handleYearChange}
        language={language}
        minYear={minYear}
        maxYear={maxYear}
        disabled={mapLayer.temporal === false}
        notice={layerRangeNotice}
      />

      {/* ANALYSIS */}
      <AnalysisPanel
        data={analysis ? { ...analysis, analysisEndYear: analysis.analysisEndYear ?? analysis.observedEndYear } : analysis}
        language={language}
        mapLayerTitle={selectedLayerTitle}
        analysisVariable={selectedVariable}
        biodiversityContext={biodiversityContext}
        regionAnalysisMode={regionAnalysisMode}
        onRegionAnalysisModeChange={(nextMode) => {
          setRegionAnalysisMode(nextMode);
          if (selectedPlace) runAnalysis(
            selectedPlace.display_name,
            selectedVariable,
            year,
            Number(selectedPlace.lat),
            Number(selectedPlace.lon),
            selectedPlace,
            nextMode,
          );
        }}
        regionModeAvailable={Boolean(selectedPlace?.geojson && getRegionBounds(selectedPlace))}
        canUsePolygonMode={Boolean(selectedPlace?.geojson && GEE_BACKED_LABELS.includes(selectedVariable))}
      />

      {analysisLoading && <div className="analysisLoading">
        {isTurkish ? "NASA verisi alınıyor..." : "Fetching NASA data..."}
      </div>}

      {modeGuide && (
        <div className="modeGuide">
          <button className="modeGuideClose" onClick={() => setModeGuide(null)}>×</button>
          <span className="panelEyebrow">{copy.explain}</span>
          <h3>{modeGuide.type === "cascade" ? (isTurkish ? "Cascade Mode nedir?" : "What is Cascade Mode?") : modeGuide.type === "impact" ? (isTurkish ? "Impact Mode nedir?" : "What is Impact Mode?") : (isTurkish ? "Draw Mode nedir?" : "What is Draw Mode?")}</h3>
          <p>{modeGuide.type === "cascade" ? (isTurkish ? "İki çevresel değişkeni yıllar içindeki gecikmeyle karşılaştırır. Örneğin yağış değişimini bitki örtüsünün sonraki yıllardaki yanıtıyla inceler. Korelasyon tek başına nedensellik kanıtı değildir." : "It compares environmental variables across year-based time lags, such as vegetation response in the years after rainfall changes. Correlation alone does not establish causation.") : modeGuide.type === "impact" ? (isTurkish ? "Seçilen bölgenin sınır kutusunda 2020 WorldPop nüfus toplamını ve 2014–2024 VIIRS gece ışığı değişimini özetler. Bunlar çevresel trendin neden olduğu etkiyi kanıtlamaz." : "It summarizes 2020 WorldPop population and 2014–2024 VIIRS nighttime-radiance change within the selected region's bounding box. These indicators do not prove effects caused by an environmental trend.") : (isTurkish ? "Küre üzerinde istediğiniz noktaya tıklayın. Ülke veya şehir yazmadan koordinatın zaman içindeki doğrulanmış NASA serisini ve istatistiklerini getirir." : "Click any point on the globe. No country or city name is required; the panel retrieves the verified NASA series and statistics for that coordinate.")}</p>
          {modeGuide.type === "cascade" && (
            <div className="cascadeTool">
              <label htmlFor="cascadeVariable">{isTurkish ? "Karşılaştırılacak ikinci değişken" : "Second variable to compare"}</label>
              <select id="cascadeVariable" value={cascadeVariable} onChange={(event) => setCascadeVariable(event.target.value)}>
                {VARIABLES.filter((variable) => GEE_BACKED_LABELS.includes(variable)).map((variable) => (
                  <option key={variable} value={variable}>{displayLabel(variable)}</option>
                ))}
              </select>
              <button className="modeGuideAction" disabled={!selectedPlace || !GEE_BACKED_LABELS.includes(selectedVariable) || cascadeLoading} onClick={runCascade}>
                {cascadeLoading ? (isTurkish ? "HESAPLANIYOR..." : "ANALYZING...") : (isTurkish ? "GECİKMELİ İLİŞKİYİ HESAPLA" : "CALCULATE LAGGED CORRELATION")}
              </button>
              {!selectedPlace && <small>{isTurkish ? "Önce haritada bir nokta seçin veya yer arayın." : "Select a point on the globe or search for a place first."}</small>}
              {selectedPlace && !GEE_BACKED_LABELS.includes(selectedVariable) && <small>{isTurkish ? "Gecikmeli karşılaştırma şu anda NASA POWER noktası yerine Earth Engine serileriyle çalışır; önce GEE tabanlı bir analiz değişkeni seçin." : "Lagged comparison currently uses Earth Engine series rather than NASA POWER point data; select a GEE-backed analysis variable first."}</small>}
              {cascadeResult && <p className="cascadeResult">{cascadeResult.error || cascadeResult.message || `${isTurkish ? "Korelasyon" : "Correlation"}: r=${cascadeResult.correlation}; ${isTurkish ? "gecikme" : "lag"}: ${cascadeResult.lag_years} ${isTurkish ? "yıl" : "years"}; p=${cascadeResult.adjusted_p_value ?? cascadeResult.p_value}. ${cascadeResult.message}`}</p>}
            </div>
          )}
          {modeGuide.type === "impact" && <div className="cascadeTool impactTool">
            <button className="modeGuideAction" disabled={impactLoading} onClick={runImpactAnalysis}>
              {impactLoading ? (isTurkish ? "HESAPLANIYOR…" : "CALCULATING…") : (isTurkish ? "BÖLGESEL MARUZİYETİ HESAPLA" : "CALCULATE REGIONAL EXPOSURE")}
            </button>
            {impactError && <p className="impactNotice" role="alert">{impactError}</p>}
            {impactResult && <div className="impactResult" aria-live="polite">
              <p>{isTurkish ? "Sınır kutusundaki tahmini nüfus" : "Estimated population in bounding box"}: <strong>{impactResult.population_total?.toLocaleString() ?? "—"}</strong></p>
              <p>{isTurkish ? "Ortalama gece ışığı farkı" : "Mean nighttime-radiance difference"}: <strong>{impactResult.viirs_change_mean == null ? "—" : `${impactResult.viirs_change_mean.toFixed(3)} ${impactResult.viirs_unit}`}</strong></p>
              <small>{impactResult.period} · WorldPop + VIIRS. {isTurkish ? "Bağlam göstergesidir; trendin nüfus üzerindeki nedensel etkisini göstermez." : "Exposure context only; it does not show a causal population impact from the selected trend."}</small>
            </div>}
          </div>}
          <button className="modeGuideAction" onClick={() => setModeGuide(null)}>{copy.close}</button>
        </div>
      )}

    </div>
  );
}
