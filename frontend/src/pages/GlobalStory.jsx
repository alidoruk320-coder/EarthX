import { useEffect, useRef, useState } from "react";
import EarthViewer from "../cesium/Viewer";
import AnnualSeriesChart from "../components/AnnualSeriesChart";
import { analyzePointGEE, analyzeSeaLevel, analyzeSeries, GEE_BACKED_LABELS, LABEL_TO_ID, NASA_POWER_LABELS } from "../services/geeApi";
import { getNasaPowerSeries, NASA_POWER_SERIES } from "../nasa/power";
import { GIBS_GALLERY_KEYS, GIBS_LAYERS } from "../nasa/earthdata";
import { getImpactExposure } from "../services/geeApi";
import { ANALYSIS_VARIABLES, ANALYSIS_VARIABLE_LABELS } from "../data/analysisVariables";

const YEARS = Object.fromEntries(ANALYSIS_VARIABLE_LABELS.map((label) => [
  label,
  [ANALYSIS_VARIABLES[label].startYear, ANALYSIS_VARIABLES[label].endYear],
]));

function getAnnualValue(series, year) {
  return series?.find((point) => point.year === year);
}

function formatValue(value) {
  return Number.isFinite(value) ? new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 3,
  }).format(value) : "—";
}

function formatPValue(value, isTurkish) {
  const numericValue = Number(value);
  if (value == null || value === "" || !Number.isFinite(numericValue)) return "—";
  if (numericValue < 0.001) return "<0.001";
  return new Intl.NumberFormat(isTurkish ? "tr-TR" : "en-US", {
    maximumFractionDigits: 3,
  }).format(numericValue);
}

export default function GlobalStory({ language = "en", onBack }) {
  const leftViewerRef = useRef(null);
  const rightViewerRef = useRef(null);
  const viewersInitializedRef = useRef(false);
  const countryRequestRef = useRef(0);
  const [countries, setCountries] = useState([]);
  const [selectedCountryCode, setSelectedCountryCode] = useState("TR");
  const [countryLoading, setCountryLoading] = useState(false);
  const [countryError, setCountryError] = useState("");
  const [site, setSite] = useState({
    name: "Türkiye",
    lat: 39.294076,
    lon: 35.231663,
    countryCode: "TR",
  });
  const [countryBounds, setCountryBounds] = useState(null);
  const [variable, setVariable] = useState("NDVI / Vegetation");
  const [selectedMapLayer, setSelectedMapLayer] = useState("ndvi");
  const [year, setYear] = useState(2002);
  const [playing, setPlaying] = useState(true);
  const [series, setSeries] = useState([]);
  const [stats, setStats] = useState(null);
  const [unit, setUnit] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [analysisSource, setAnalysisSource] = useState(null);
  const [analysisEndYear, setAnalysisEndYear] = useState(null);
  const [speciesYearCounts, setSpeciesYearCounts] = useState({});
  const [impact, setImpact] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [speciesError, setSpeciesError] = useState("");
  const [contrastOpen, setContrastOpen] = useState(false);
  const [contrastLoading, setContrastLoading] = useState(false);
  const [contrastError, setContrastError] = useState("");
  const [contrastResults, setContrastResults] = useState([]);
  const [contrastPoints, setContrastPoints] = useState([
    { id: "atlantic", name: "Mid-Atlantic, offshore USA", lat: "36", lon: "-70" },
    { id: "pacific", name: "Western tropical Pacific", lat: "15", lon: "150" },
  ]);
  const isTurkish = language === "tr";
  const sourceName = analysisSource || ANALYSIS_VARIABLES[variable]?.source || "NASA data source";
  const storyLayer = selectedMapLayer;
  const mapLayer = GIBS_LAYERS[storyLayer];
  const [startYear, endYear] = YEARS[variable];
  const occurrenceStartYear = Math.max(startYear, 1980);
  const comparisonYear = Math.min(year, endYear);
  const mapBaselineYear = Math.max(mapLayer.minYear, Math.min(startYear, mapLayer.maxYear));
  const mapEndYear = Math.max(mapLayer.minYear, Math.min(comparisonYear, mapLayer.maxYear));
  const timelineStartYear = Math.max(startYear, mapLayer.minYear);
  const timelineEndYear = Math.min(endYear, mapLayer.maxYear);
  const analysisStartYearDisplay = startYear;
  const baseline = getAnnualValue(series, startYear);
  const current = getAnnualValue(series, comparisonYear);
  const baselineSpeciesCount = speciesYearCounts[startYear];
  const currentSpeciesCount = speciesYearCounts[comparisonYear];

  useEffect(() => {
    let active = true;
    fetch("https://api.first.org/data/v1/countries?limit=300")
      .then(async (response) => {
        if (!response.ok) throw new Error(`Country directory error (${response.status})`);
        const payload = await response.json();
        return Object.entries(payload.data || {})
          .map(([code, entry]) => ({ code, name: entry.country }))
          .sort((left, right) => left.name.localeCompare(right.name));
      })
      .then((items) => {
        if (active) setCountries(items);
      })
      .catch((loadError) => {
        if (active) setCountryError(loadError.message);
      });
    return () => {
      active = false;
      countryRequestRef.current += 1;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const requestId = countryRequestRef.current;
    const query = new URLSearchParams({
      country: "Turkey",
      format: "jsonv2",
      limit: "1",
      polygon_geojson: "1",
    });
    fetch(`https://nominatim.openstreetmap.org/search?${query}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Country boundary request failed (${response.status})`);
        return response.json();
      })
      .then((places) => {
        const place = places[0];
        if (!place || controller.signal.aborted || requestId !== countryRequestRef.current) return;
        const bounds = place.boundingbox?.map(Number);
        setCountryBounds(bounds?.length === 4 && bounds.every(Number.isFinite) ? bounds : null);
        if (place.geojson) {
          setSite((currentSite) => ({
            ...currentSite,
            lat: Number(place.lat),
            lon: Number(place.lon),
            geometry: place.geojson,
          }));
        }
      })
      .catch((loadError) => {
        if (!controller.signal.aborted) console.warn("Could not load the default country boundary:", loadError);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!viewersInitializedRef.current) {
      viewersInitializedRef.current = true;
      return;
    }
    leftViewerRef.current?.setGibsLayer(storyLayer, mapBaselineYear);
    rightViewerRef.current?.setGibsLayer(storyLayer, mapEndYear);
    if (site.geometry) {
      Promise.all([
        leftViewerRef.current?.setSearchBoundary(site.geometry),
        rightViewerRef.current?.setSearchBoundary(site.geometry),
      ]).then(([leftShown, rightShown]) => {
        if (!leftShown) leftViewerRef.current?.flyTo(site.lat, site.lon);
        if (!rightShown) rightViewerRef.current?.flyTo(site.lat, site.lon);
      });
    } else {
      leftViewerRef.current?.flyTo(site.lat, site.lon);
      rightViewerRef.current?.flyTo(site.lat, site.lon);
    }
  }, [storyLayer, mapBaselineYear, mapEndYear, site]);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setInterval(() => {
      setYear((currentYear) => {
        if (currentYear >= timelineEndYear) {
          setPlaying(false);
          return timelineEndYear;
        }
        return currentYear + 1;
      });
    }, 1800);
    return () => window.clearInterval(timer);
  }, [timelineEndYear, playing]);

  useEffect(() => {
    let active = true;
    const analysisStartYear = startYear;
    const sourceEndYear = endYear;
    const query = new URLSearchParams({
      country: site.countryCode,
      year: `${occurrenceStartYear},${endYear}`,
      hasCoordinate: "true",
      facet: "year",
      facetLimit: String(endYear - occurrenceStartYear + 1),
      limit: "0",
    });

    setLoading(true);
    setError("");
    setSpeciesError("");
    setSeries([]);
    setStats(null);
    setUnit(null);
    setDataset(null);
    setAnalysisSource(null);
    setAnalysisEndYear(sourceEndYear);
    setYear((currentYear) => Math.max(startYear, Math.min(currentYear, endYear)));
    setSpeciesYearCounts({});

    const analysisRequest = variable === "Sea Level"
      ? analyzeSeaLevel(site.lat, site.lon, analysisStartYear, sourceEndYear)
      : NASA_POWER_LABELS.includes(variable)
        ? getNasaPowerSeries(site.lat, site.lon, variable, analysisStartYear, sourceEndYear)
          .then(async (observations) => {
            const source = NASA_POWER_SERIES[variable];
            const datasetId = `NASA POWER daily parameter ${source.parameter}`;
            const calculated = observations.length >= 8
              ? await analyzeSeries(observations, variable, source.unit, datasetId, analysisStartYear, sourceEndYear)
              : null;
            return {
              raw_series: observations,
              trend: calculated?.trend || "insufficient_data",
              sen_slope: calculated?.sen_slope ?? null,
              z_score: calculated?.z_score ?? null,
              p_value: calculated?.p_value ?? null,
              significant: calculated?.significant ?? false,
              message: calculated?.message || "At least 8 annual observations are required.",
              unit: source.unit,
              dataset_id: datasetId,
              source: "NASA POWER",
            };
          })
      : GEE_BACKED_LABELS.includes(variable)
        ? analyzePointGEE(site.lat, site.lon, variable, analysisStartYear, sourceEndYear)
        : Promise.reject(new Error(`No analysis provider configured for ${variable}`));

    Promise.allSettled([
      analysisRequest,
      fetch(`https://api.gbif.org/v1/occurrence/search?${query}`).then(async (response) => {
        if (!response.ok) throw new Error(`GBIF API error (${response.status})`);
        return response.json();
      }),
    ]).then(([analysisResult, speciesResult]) => {
      if (!active) return;
      if (analysisResult.status === "fulfilled") {
        const analysis = analysisResult.value;
        setSeries((analysis.raw_series || []).map((point) => ({
          year: Number(point.year || point.date?.slice(0, 4)),
          value: Number(point.value),
        })));
        setStats(analysis);
        setUnit(analysis.unit);
        setDataset(ANALYSIS_VARIABLES[variable]?.datasetId || analysis.dataset_id);
        setAnalysisSource(analysis.source || ANALYSIS_VARIABLES[variable]?.source || "NASA data source");
      } else {
        setError(analysisResult.reason.message);
      }
      if (speciesResult.status === "fulfilled") {
        setSpeciesYearCounts(Object.fromEntries(
          (speciesResult.value.facets?.[0]?.counts || []).map((item) => [
          Number(item.name),
          item.count,
          ])
        ));
      } else {
        setSpeciesError(speciesResult.reason.message);
      }
    }).finally(() => {
      if (active) setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [site, variable, startYear, endYear]);

  useEffect(() => {
    if (!countryBounds) {
      setImpact(null);
      setImpactError("");
      setImpactLoading(false);
      return undefined;
    }
    const [south, north, west, east] = countryBounds;
    if (![south, north, west, east].every(Number.isFinite)) return undefined;
    const controller = new AbortController();
    setImpactLoading(true);
    setImpactError("");
    setImpact(null);

    async function fetchImpact() {
      try {
        const exposure = await getImpactExposure({ south, north, west, east }, controller.signal);
        if (!controller.signal.aborted) {
          setImpact(exposure);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setImpactError(error.message || (isTurkish ? "Bölgesel etki verisi alınamadı." : "Regional exposure data is unavailable."));
        }
      } finally {
        if (!controller.signal.aborted) setImpactLoading(false);
      }
    }

    fetchImpact();
    return () => controller.abort();
  }, [countryBounds, isTurkish]);

  function selectVariable(nextVariable) {
    setPlaying(false);
    setVariable(nextVariable);
    const [nextStartYear, nextEndYear] = YEARS[nextVariable];
    const minimum = Math.max(nextStartYear, mapLayer.minYear);
    const maximum = Math.min(nextEndYear, mapLayer.maxYear);
    setYear(Math.max(minimum, Math.min(year, maximum)));
  }

  function selectMapLayer(nextLayer) {
    setPlaying(false);
    setSelectedMapLayer(nextLayer);
    const layer = GIBS_LAYERS[nextLayer];
    const minimum = Math.max(startYear, layer.minYear);
    const maximum = Math.min(endYear, layer.maxYear);
    setYear(Math.max(minimum, Math.min(year, maximum)));
  }

  async function runContrastingSeaLevelDemo() {
    const validPoints = contrastPoints.map((point) => ({
      ...point,
      lat: Number(point.lat),
      lon: Number(point.lon),
    }));
    if (validPoints.some((point) => !Number.isFinite(point.lat) || !Number.isFinite(point.lon)
      || point.lat < -90 || point.lat > 90 || point.lon < -180 || point.lon > 180)) {
      setContrastError(isTurkish ? "Koordinatları kontrol edin: enlem −90–90, boylam −180–180 olmalı." : "Check coordinates: latitude must be −90 to 90 and longitude −180 to 180.");
      return;
    }
    setContrastLoading(true);
    setContrastError("");
    setContrastResults([]);
    try {
      const results = await Promise.all(validPoints.map(async (point) => ({
        ...point,
        analysis: await analyzeSeaLevel(point.lat, point.lon, 1993, 2007),
      })));
      setContrastResults(results);
    } catch (loadError) {
      setContrastError(loadError.message || (isTurkish ? "NASA/JPL karşılaştırma verisi alınamadı." : "NASA/JPL comparison data could not be loaded."));
    } finally {
      setContrastLoading(false);
    }
  }

  async function selectCountry(code) {
    const requestId = ++countryRequestRef.current;
    const country = countries.find((item) => item.code === code);
    if (!country) return;
    setCountryLoading(true);
    setCountryError("");
    try {
      const query = new URLSearchParams({
        country: country.name,
        countrycodes: code.toLowerCase(),
        format: "jsonv2",
        limit: "1",
        addressdetails: "1",
        polygon_geojson: "1",
      });
      const response = await fetch(`https://nominatim.openstreetmap.org/search?${query}`);
      if (!response.ok) throw new Error(`Country geocoding error (${response.status})`);
      const places = await response.json();
      const place = places.find((item) => item.address?.country_code?.toUpperCase() === code) || places[0];
      if (!place) throw new Error(isTurkish ? "Ülke merkezi bulunamadı." : "Country location was not found.");
      if (requestId !== countryRequestRef.current) return;
      setSelectedCountryCode(code);
      const boundingBox = Array.isArray(place.boundingbox) && place.boundingbox.length === 4
        ? place.boundingbox.map(Number)
        : null;
      const geometry = place.geojson || null;
      setCountryBounds(boundingBox && boundingBox.every(Number.isFinite) ? boundingBox : null);
      setSite({
        name: country.name,
        lat: Number(place.lat),
        lon: Number(place.lon),
        countryCode: code,
        geometry,
      });
    } catch (loadError) {
      if (requestId === countryRequestRef.current) setCountryError(loadError.message);
    } finally {
      if (requestId === countryRequestRef.current) setCountryLoading(false);
    }
  }

  const copy = {
    back: isTurkish ? "← KÜRESEL GÖRÜNÜME DÖN" : "← BACK TO GLOBE",
    eyebrow: isTurkish ? "UYDU VERİSİ + GBIF TÜR KAYITLARI" : "SATELLITE DATA + GBIF SPECIES RECORDS",
    title: isTurkish ? "Dünya sistemi: ölçülen değişim" : "Earth system: observed change",
    intro: isTurkish
      ? "İki kürede başlangıç ve seçili yılın uydu görüntülerini karşılaştır. Nokta trendi ayrı NASA/Google Earth Engine ölçümlerinden, canlı gözlem kayıtları GBIF'ten gelir; kayıt sayıları hayvan sayısı değildir."
      : "Compare baseline and selected-year satellite imagery on two globes. The point trend uses separate NASA/Google Earth Engine measurements; species occurrence records come from GBIF and are not animal counts.",
    site: isTurkish ? "İncelenecek bölge" : "Study region",
    baseline: isTurkish ? "BAŞLANGIÇ" : "BASELINE",
    selected: isTurkish ? "SEÇİLİ YIL" : "SELECTED YEAR",
    mapLayer: isTurkish ? "Uydu veri katmanı" : "Satellite data layer",
    analysisVariable: isTurkish ? "Trend analiz değişkeni" : "Trend analysis variable",
    play: isTurkish ? "▶ HİKÂYEYİ OYNAT" : "▶ PLAY STORY",
    pause: isTurkish ? "Ⅱ DURAKLAT" : "Ⅱ PAUSE",
    dataPoint: isTurkish ? "Yıllık model/uydu gözlemi" : "Annual model / satellite observation",
    trend: isTurkish ? "Dönem eğilimi" : "Period trend",
    speciesRecords: isTurkish ? "GBIF biyoçeşitlilik kayıtları" : "GBIF biodiversity records",
    recordsDisclaimer: isTurkish
      ? "Kayıt sayısı popülasyon büyüklüğü değildir; GBIF kayıtları gözlem ve veri gönderim çabasına bağlıdır."
      : "Record counts are not population abundance; GBIF occurrence records depend on observation and reporting effort.",
    nasaDisclaimer: ANALYSIS_VARIABLES[variable]?.description?.[isTurkish ? "tr" : "en"] || "",
    occurrenceYears: isTurkish
          ? `GBIF, tarih seçicisinden bağımsız olarak ${occurrenceStartYear}–${endYear} dönemindeki kayıtları kapsar.`
      : `GBIF records cover ${occurrenceStartYear}–${endYear}, independently of the selected imagery year.`,
    source: isTurkish ? "VERİ KAYNAKLARI" : "DATA SOURCES",
  };
  const validTrendTest = stats?.p_value != null && Number.isFinite(Number(stats.p_value));
  const localizedTrend = stats?.trend?.toLowerCase() === "insufficient_data"
    ? (isTurkish ? "İstatistiksel test için yetersiz veya aralıklı veri" : "Insufficient or discontinuous data for significance test")
    : stats?.trend?.toLowerCase() === "no trend"
    ? (isTurkish ? "İstatistiksel olarak anlamlı monoton trend saptanmadı" : "No statistically significant monotonic trend detected")
    : stats?.trend?.toLowerCase() === "increasing"
      ? (isTurkish ? "Artış" : "Increasing")
      : stats?.trend?.toLowerCase() === "decreasing"
        ? (isTurkish ? "Azalış" : "Decreasing")
        : stats?.trend;
  const contrastSlopes = contrastResults.map(({ analysis }) => Number(analysis.sen_slope));
  const contrastHasSlopes = contrastSlopes.length === 2 && contrastSlopes.every(Number.isFinite);
  const contrastHasOppositeSigns = contrastHasSlopes
    && contrastSlopes[0] !== 0
    && contrastSlopes[1] !== 0
    && Math.sign(contrastSlopes[0]) !== Math.sign(contrastSlopes[1]);

  return (
    <main className="globalStoryPage">
      <header className="globalStoryHeader">
        <button className="globalStoryBack" onClick={onBack}>{copy.back}</button>
        <div className="globalStoryHeading">
          <div className="globalStoryEyebrow">{copy.eyebrow}</div>
          <h1>{copy.title}</h1>
          <p>{copy.intro}</p>
        </div>
        <div className="globalStoryControls">
          <label>
            {copy.site}
            <select value={selectedCountryCode} onChange={(event) => selectCountry(event.target.value)} disabled={countryLoading}>
              {selectedCountryCode === "TR" && !countries.some((item) => item.code === "TR") && <option value="TR">Türkiye</option>}
              {countries.map((item) => <option key={item.code} value={item.code}>{item.name}</option>)}
            </select>
          </label>
          <label>
            {isTurkish ? "Analiz enlemi" : "Analysis latitude"}
            <input type="number" min="-90" max="90" step="0.1" value={site.lat} onChange={(event) => {
              const lat = Number(event.target.value);
              if (Number.isFinite(lat) && lat >= -90 && lat <= 90) setSite((currentSite) => ({ ...currentSite, lat }));
            }} />
          </label>
          <label>
            {isTurkish ? "Analiz boylamı" : "Analysis longitude"}
            <input type="number" min="-180" max="180" step="0.1" value={site.lon} onChange={(event) => {
              const lon = Number(event.target.value);
              if (Number.isFinite(lon) && lon >= -180 && lon <= 180) setSite((currentSite) => ({ ...currentSite, lon }));
            }} />
          </label>
          <label>
            {copy.mapLayer}
            <select value={selectedMapLayer} onChange={(event) => selectMapLayer(event.target.value)}>
              {GIBS_GALLERY_KEYS.map((key) => (
                <option key={key} value={key}>{GIBS_LAYERS[key].title}</option>
              ))}
            </select>
          </label>
          <label>
            {copy.analysisVariable}
            <select value={variable} onChange={(event) => selectVariable(event.target.value)}>
              {ANALYSIS_VARIABLE_LABELS.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
          {countryLoading && <small className="countryStatus">{isTurkish ? "Ülke merkezi aranıyor…" : "Finding country location…"}</small>}
          {countryError && <small className="countryStatus countryError">{countryError}</small>}
      {impactLoading && <small className="countryStatus">{isTurkish ? "Bölgesel etki verisi hesaplanıyor…" : "Calculating regional exposure…"}</small>}
      {impactError && <small className="countryStatus countryError">{impactError}</small>}
        </div>
      </header>

      <section className="storyGlobeComparison" aria-label={copy.title}>
        <article className="storyGlobeCard">
          <h2>{copy.baseline} · {mapBaselineYear}</h2>
          <EarthViewer
            ref={leftViewerRef}
            containerId="storyBaselineGlobe"
            initialYear={mapBaselineYear}
            initialLayer={storyLayer}
            initialLocation={site}
          />
        </article>
        <article className="storyGlobeCard">
          <h2>{copy.selected} · {mapEndYear}</h2>
          <EarthViewer
            ref={rightViewerRef}
            containerId="storyCurrentGlobe"
            initialYear={mapEndYear}
            initialLayer={storyLayer}
            initialLocation={site}
          />
        </article>
      </section>

      <section className="contrastDemo" aria-labelledby="contrastDemoTitle">
        <div className="contrastDemoHeading">
          <div>
            <span>{isTurkish ? "CHALLENGE DEMOSU · AYNI DEĞİŞKEN, İKİ BÖLGE" : "CHALLENGE DEMO · SAME VARIABLE, TWO REGIONS"}</span>
            <h2 id="contrastDemoTitle">{isTurkish ? "Okyanus seviyesindeki bölgesel zıtlık" : "Regional contrast in sea level"}</h2>
            <p>{isTurkish
              ? "NASA, 1993–2007 arasında Batı Pasifik'te yaygın yükseliş ve ABD orta Atlantik açıklarında deniz seviyesi düşüş alanı bildirdi. Aşağıdaki iki NASA/JPL hücresinin yıllık serileri ve testleri canlı yüklenir; bu, NASA haritasının birebir yeniden üretimi değildir."
              : "NASA reported widespread sea-surface-height rise in the western Pacific and a decline area off the U.S. mid-Atlantic during 1993–2007. The annual series and tests for the two NASA/JPL cells below load live; this is not an exact reproduction of NASA's map."}</p>
          </div>
          <button type="button" onClick={() => {
            setContrastOpen((open) => !open);
            if (!contrastOpen && contrastResults.length === 0) runContrastingSeaLevelDemo();
          }}>
            {contrastOpen
              ? (isTurkish ? "DEMOYU KAPAT" : "CLOSE DEMO")
              : (isTurkish ? "KARŞILAŞTIRMAYI YÜKLE" : "LOAD COMPARISON")}
          </button>
        </div>
        {contrastOpen && <>
          <div className="contrastPointControls">
            {contrastPoints.map((point, index) => (
              <label key={point.id}>
                {index === 0
                  ? (isTurkish ? "AÇIK ATLANTİK HÜCRESİ" : "ATLANTIC OCEAN CELL")
                  : (isTurkish ? "BATI PASİFİK HÜCRESİ" : "WESTERN PACIFIC CELL")}
                <span>{point.name}</span>
                <div>
                  <input aria-label={`${point.name} latitude`} disabled={contrastLoading} type="number" min="-90" max="90" step="0.1" value={point.lat} onChange={(event) => { setContrastResults([]); setContrastPoints((currentPoints) => currentPoints.map((item) => item.id === point.id ? { ...item, lat: event.target.value } : item)); }} />
                  <input aria-label={`${point.name} longitude`} disabled={contrastLoading} type="number" min="-180" max="180" step="0.1" value={point.lon} onChange={(event) => { setContrastResults([]); setContrastPoints((currentPoints) => currentPoints.map((item) => item.id === point.id ? { ...item, lon: event.target.value } : item)); }} />
                </div>
              </label>
            ))}
            <button type="button" disabled={contrastLoading} onClick={runContrastingSeaLevelDemo}>
              {contrastLoading ? (isTurkish ? "NASA/JPL VERİSİ YÜKLENİYOR…" : "LOADING NASA/JPL DATA…") : (isTurkish ? "1993–2007 DÖNEMİNİ ANALİZ ET" : "ANALYZE 1993–2007")}
            </button>
          </div>
          {contrastError && <p className="storyError" role="alert">{contrastError}</p>}
          {contrastLoading && <p role="status">{isTurkish ? "İki okyanus zaman serisi alınıp analiz ediliyor…" : "Retrieving and analyzing both ocean time series…"}</p>}
          {contrastResults.length === 2 && <div className="contrastResults">
            {contrastResults.map(({ id, name, lat, lon, analysis }) => (
              <article key={id}>
                <h3>{name}</h3>
                <p>{analysis.trend} · Sen {formatValue(analysis.sen_slope)} {analysis.unit}/yr · p={formatPValue(analysis.p_value, isTurkish)}</p>
                <p>{analysis.significant
                  ? (isTurkish ? "p < 0,05: anlamlı trend" : "p < 0.05: significant trend")
                  : (isTurkish ? "p ≥ 0,05 veya test için yetersiz veri" : "p ≥ 0.05 or insufficient data for a significance test")}</p>
                <small>{lat.toFixed(1)}°, {lon.toFixed(1)}° · 1993–2007 · {analysis.observation_count ?? analysis.raw_series?.length ?? 0} {isTurkish ? "yıllık gözlem" : "annual observations"} · {analysis.source} · {analysis.dataset_id}</small>
                <AnnualSeriesChart series={analysis.raw_series || []} slope={analysis.sen_slope} unit={analysis.unit || ""} language={language} />
              </article>
            ))}
            <p className="contrastConclusion">
              {!contrastHasSlopes
                ? (isTurkish ? "Bu iki hücreden en az biri için eğim hesaplanamadı; karşıt yön değerlendirmesi yapılamıyor." : "A slope could not be estimated for at least one cell, so opposite directions cannot be assessed.")
                : contrastHasOppositeSigns
                ? (isTurkish ? "Bu iki seçili hücrede Sen eğimleri zıt yönlü. p-değerlerini ayrı ayrı değerlendirin; zıt işaret tek başına iki trendin de anlamlı olduğunu göstermez." : "The Sen slopes at these two cells have opposite signs. Assess each p-value separately; opposite signs alone do not mean both trends are significant.")
                : (isTurkish ? "Bu hücrelerde eğim işaretleri zıt değil. Bölgesel örüntü koordinata ve döneme duyarlıdır; NASA'nın kaynak haritası ile birebir karşılaştırma için koordinatları düzenleyip yeniden analiz edin." : "The slope signs at these cells are not opposite. Regional patterns depend on location and period; adjust the coordinates and rerun to compare with NASA's source map.")}
            </p>
          </div>}
          <p className="contrastCitation">
            <a href="https://science.nasa.gov/earth/earth-observatory/regional-patterns-of-sea-level-change-1993-2007-8875/" target="_blank" rel="noreferrer">{isTurkish ? "NASA Earth Observatory · Bölgesel deniz seviyesi örüntüleri, 1993–2007 ↗" : "NASA Earth Observatory · Regional Patterns of Sea Level Change, 1993–2007 ↗"}</a>
            <span>{isTurkish ? "NASA/JPL ürünü yaklaşık 1° okyanus hücresidir; kıyı gelgit ölçümü değildir. Test, yıllık hücre serisine Hamed–Rao düzeltmeli Mann–Kendall uygular." : "NASA/JPL values are approximately 1° ocean cells, not coastal tide-gauge measurements. The test applies Hamed–Rao modified Mann–Kendall to each annual cell series."}</span>
          </p>
        </>}
      </section>

      <section className="storyEvidence">
        <div className="storyTimeline">
          <div className="storyTimelineHeader">
            <strong>{startYear}</strong>
            <strong>{mapEndYear}</strong>
            <span>{endYear}</span>
          </div>
          <input
            aria-label={copy.selected}
            type="range"
            min={timelineStartYear}
            max={timelineEndYear}
            value={comparisonYear}
            onChange={(event) => {
              setPlaying(false);
              setYear(Number(event.target.value));
            }}
          />
          <button onClick={() => setPlaying((value) => !value)}>
            {playing ? copy.pause : copy.play}
          </button>
        </div>

        <p className="storyNarrative">
          {loading
            ? (isTurkish ? "Uydu ölçümleri ve tür gözlem kayıtları yükleniyor." : "Loading satellite measurements and species records.")
            : error
              ? (isTurkish
                ? `${sourceName} ölçümü alınamadı: ${error}`
                : `${sourceName} measurement unavailable: ${error}`)
              : isTurkish
                ? `${site.name} noktasında ${sourceName} ${dataset || variable} ölçümü ${startYear} yılında ${formatValue(baseline?.value)}${unit ? ` ${unit}` : ""}, ${comparisonYear} yılında ${formatValue(current?.value)}${unit ? ` ${unit}` : ""} oldu. GBIF'in aynı bölge için kayıtları ${baselineSpeciesCount ?? "—"} ve ${currentSpeciesCount ?? "—"}; bu kayıt farkı popülasyon sayısı değildir ve gözlem çabasından etkilenebilir.`
                : `At the ${site.name} point, ${sourceName} ${dataset || variable} measured ${formatValue(baseline?.value)}${unit ? ` ${unit}` : ""} in ${startYear} and ${formatValue(current?.value)}${unit ? ` ${unit}` : ""} in ${comparisonYear}. GBIF records for the same area are ${baselineSpeciesCount ?? "—"} and ${currentSpeciesCount ?? "—"}; this difference is not a population count and may reflect observation effort.`}
        </p>

        <div className="storyFacts">
          <article>
            <h3>{copy.dataPoint}</h3>
            {loading ? <p>{isTurkish ? "Uydu verisi alınıyor…" : "Loading satellite observations…"}</p> : error
              ? <p className="storyError">{error}</p>
              : <>
                <p>{startYear}: <strong>{formatValue(baseline?.value)} {unit || ""}</strong></p>
                <p>{comparisonYear}: <strong>{formatValue(current?.value)} {unit || ""}</strong></p>
                <small>{sourceName} · {ANALYSIS_VARIABLES[variable]?.temporalResolution} · {analysisStartYearDisplay}–{analysisEndYear ?? endYear} · {site.lat.toFixed(2)}°, {site.lon.toFixed(2)}° · {dataset || ANALYSIS_VARIABLES[variable]?.datasetId || (isTurkish ? "Ürün bilgisi yok" : "Product ID unavailable")}</small>
              </>}
          </article>
          <article>
            <h3>{copy.trend}</h3>
            {stats && validTrendTest ? (
              <>
                <p>{localizedTrend} · Sen slope {formatValue(stats.sen_slope)} {unit || ""}/yr</p>
                <p>p = {formatPValue(stats.p_value, isTurkish)} · {stats.significant
                  ? (isTurkish ? "istatistiksel olarak anlamlı" : "statistically significant")
                  : (isTurkish ? "istatistiksel olarak anlamlı değil" : "not statistically significant")}</p>
                <small>{analysisStartYearDisplay}–{analysisEndYear ?? endYear} · {series.length} {isTurkish ? "yıllık gözlem" : "annual observations"} · {isTurkish ? "Hamed–Rao düzeltmeli Mann–Kendall" : "Hamed–Rao modified Mann–Kendall"}</small>
              </>
            ) : <p>{loading ? "…" : stats?.message || (isTurkish ? "Doğrulanmış dönem eğilimi yok." : "No verified period trend.")}</p>}
            <small>{copy.nasaDisclaimer}</small>
          </article>
          <article>
            <h3>{copy.speciesRecords}</h3>
            {speciesError
              ? <p className="storyError">{speciesError}</p>
              : <p>{startYear}: <strong>{baselineSpeciesCount ?? "—"}</strong> · {comparisonYear}: <strong>{currentSpeciesCount ?? "—"}</strong></p>}
            <small>{copy.recordsDisclaimer}</small>
            <small>{copy.occurrenceYears}</small>
          </article>
        </div>

        <AnnualSeriesChart
          series={series}
          slope={stats?.sen_slope}
          unit={unit || ""}
          language={language}
        />

        <section className="storyImpact">
          <h2>{isTurkish ? "Bölgesel etki göstergeleri" : "Regional impact indicators"}</h2>
          <p>{isTurkish
            ? "Ülke sınır kutusundaki nüfus ızgarası ve NASA gece ışığı verileri; nüfus yoğunluğu, gece ışığı değişimi ve bunlara maruz kalan yaklaşık nüfus alanı. Bunlar çevresel trendin nedensel etkisini kanıtlamaz."
    : "WorldPop population and VIIRS nighttime-radiance indicators for the selected country's bounding box. These describe exposure and human activity; they do not establish a causal impact from an environmental trend."}</p>
          {impact ? <div className="storyImpactGrid">
            <span>{isTurkish ? "Kapsanan nüfus" : "Population covered"}<strong>{impact.population_total?.toLocaleString() ?? "—"}</strong></span>
            <span>{isTurkish ? "Ortalama gece ışığı farkı" : "Mean night-radiance difference"}<strong>{impact.viirs_change_mean == null ? "—" : `${formatValue(impact.viirs_change_mean)} ${impact.viirs_unit}`}</strong></span>
            <span>{isTurkish ? "Veri dönemi" : "Data period"}<strong>{impact.period || "—"}</strong></span>
          </div> : !impactLoading && !impactError && <small>{isTurkish ? "Bu alan çevresel trendin neden olduğu nüfus etkisini değil, yalnızca maruziyet bağlamını gösterir." : "This panel reports exposure context, not population impacts caused by an environmental trend."}</small>}
          {impact && <small>{isTurkish ? "Nüfus 2020 WorldPop ızgarasından ülke sınır kutusunda yaklaşık 1 km ölçekte hesaplandı; ışık farkı 2014 ve 2024 yıllık alan ortalamalarının farkıdır. Nedensel etki değildir." : "Population is summed from the 2020 WorldPop grid within the country's bounding box at approximately 1 km scale; radiance change is the difference between 2014 and 2024 annual area means. This is not a causal impact."}</small>}
        </section>

        <footer className="storySources">
          <strong>{copy.source}</strong>
          {dataset && <a href={`https://developers.google.com/earth-engine/datasets/catalog/${dataset.replaceAll("/", "_")}`} target="_blank" rel="noreferrer">Earth Engine dataset documentation</a>}
          <a href="https://www.gbif.org/developer/occurrence" target="_blank" rel="noreferrer">GBIF occurrence API</a>
          <a href="https://grace.jpl.nasa.gov/data/get-data/" target="_blank" rel="noreferrer">NASA/JPL GRACE data</a>
          <a href="https://www.earthdata.nasa.gov/data/tools/worldview" target="_blank" rel="noreferrer">NASA Worldview / GIBS</a>
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap / Nominatim geocoding</a>
          <a href="https://power.larc.nasa.gov/docs/services/api/temporal/daily/" target="_blank" rel="noreferrer">NASA POWER daily API</a>
          <a href="https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008" target="_blank" rel="noreferrer">NASA SMAP L4 catalog</a>
          <a href="https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_LAND" target="_blank" rel="noreferrer">NASA GRACE V04 catalog</a>
          <a href="https://earth.esa.int/eogateway/catalog/smos-science-products" target="_blank" rel="noreferrer">ESA SMOS L1/L2 science products (reference; not integrated)</a>
          <a href="https://earth.esa.int/eogateway/catalog/smos-nrt-data-products" target="_blank" rel="noreferrer">ESA SMOS NRT products (reference; not integrated)</a>
          <a href="https://developers.google.com/earth-engine/datasets/catalog/WorldPop_GP_100m_pop_age_sex_cons_unadj" target="_blank" rel="noreferrer">WorldPop 100 m population data</a>
          <a href="https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP46A2" target="_blank" rel="noreferrer">NASA VIIRS Black Marble nighttime radiance</a>
        </footer>
      </section>
    </main>
  );
}
