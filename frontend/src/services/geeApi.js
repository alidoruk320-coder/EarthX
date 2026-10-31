const API_BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

export const LABEL_TO_ID = {
  Temperature: "temperature",
  "NDVI / Vegetation": "ndvi",
  "GRACE Total Water Storage Anomaly": "grace_tws",
  "Soil Moisture": "soil_moisture",
  Precipitation: "precipitation",
  "GPM Precipitation Rate": "gpm_precipitation",
  "Total Column Ozone": "total_column_ozone",
  "MERRA-2 Air Temperature": "merra2_t2m",
  "MERRA-2 Precipitable Water": "merra2_precipitable_water",
  "MERRA-2 Evaporation Rate": "merra2_evaporation",
  "GLDAS Root-Zone Soil Moisture": "gldas_root_moisture",
  "GLDAS Surface Runoff": "gldas_surface_runoff",
};

export const GEE_BACKED_LABELS = [
  "NDVI / Vegetation",
  "Soil Moisture",
  "GRACE Total Water Storage Anomaly",
  "GPM Precipitation Rate",
  "Total Column Ozone",
  "MERRA-2 Air Temperature",
  "MERRA-2 Precipitable Water",
  "MERRA-2 Evaporation Rate",
  "GLDAS Root-Zone Soil Moisture",
  "GLDAS Surface Runoff",
];

export const NASA_POWER_LABELS = ["Temperature", "Precipitation"];

async function request(path, options) {
  const { timeoutMs, timeoutMessage, ...fetchOptions } = options || {};
  const timeoutController = timeoutMs ? new AbortController() : null;
  const timeoutId = timeoutController
    ? setTimeout(() => timeoutController.abort(), timeoutMs)
    : null;
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      ...(timeoutController ? { signal: timeoutController.signal } : {}),
    });
  } catch (error) {
    if (timeoutController?.signal.aborted) {
      const timeoutError = new Error(timeoutMessage || "Analysis request timed out");
      timeoutError.code = "ANALYSIS_TIMEOUT";
      throw timeoutError;
    }
    throw error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const error = new Error(detail?.detail || `Earth Engine API error (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

export function getTileUrl(variableLabel, year) {
  const variableId = LABEL_TO_ID[variableLabel];
  if (!variableId) return Promise.resolve(null);
  return request(`/tile-url/${variableId}/${year}`).then((result) => result.tile_url);
}

export function getChangeTileUrl(variableLabel, startYear, endYear) {
  const variableId = LABEL_TO_ID[variableLabel];
  if (!variableId) return Promise.resolve(null);
  return request(`/change-tile-url/${variableId}/${startYear}/${endYear}`)
    .then((result) => result.tile_url);
}

export function analyzePointGEE(lat, lon, variableLabel, startYear, endYear) {
  const variable = LABEL_TO_ID[variableLabel];
  if (!variable) throw new Error(`Unsupported Earth Engine variable: ${variableLabel}`);
  return request("/analyze-point", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, variable, start_year: startYear, end_year: endYear }),
  });
}

export function analyzeRegionGEE(geometry, variableLabel, startYear, endYear) {
  const variable = LABEL_TO_ID[variableLabel];
  if (!variable) throw new Error(`Unsupported Earth Engine variable: ${variableLabel}`);
  return request("/analyze-region", {
    timeoutMs: 180_000,
    timeoutMessage: "Alan-ağırlıklı poligon analizi 3 dakika içinde tamamlanamadı. Daha küçük bir bölge veya Hızlı tahmin modunu deneyin.",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ geometry, variable, start_year: startYear, end_year: endYear }),
  });
}

export function analyzeSampledSoilMoistureRegion(geometry, samplePoints, startYear, endYear) {
  return request("/analyze-region", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      geometry,
      variable: "soil_moisture",
      start_year: startYear,
      end_year: endYear,
      sampling_method: "sampled_boundary_filtered",
      sample_points: samplePoints.map(({ lat, lon, weight }) => ({ lat, lon, weight })),
    }),
  });
}

export function analyzeSampledRegionGEE(geometry, variableLabel, samplePoints, startYear, endYear) {
  const variable = LABEL_TO_ID[variableLabel];
  if (!variable) throw new Error(`Unsupported Earth Engine variable: ${variableLabel}`);
  return request("/analyze-region", {
    timeoutMs: 180_000,
    timeoutMessage: "Hızlı bölgesel analiz 3 dakika içinde tamamlanamadı. Daha küçük bir bölge veya daha kısa dönem seçin.",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      geometry,
      variable,
      start_year: startYear,
      end_year: endYear,
      sampling_method: "sampled_boundary_filtered",
      sample_points: samplePoints.map(({ lat, lon, weight }) => ({ lat, lon, weight })),
    }),
  });
}

export function analyzePoint(lat, lon, variableLabel, startYear, endYear) {
  if (GEE_BACKED_LABELS.includes(variableLabel)) {
    return analyzePointGEE(lat, lon, variableLabel, startYear, endYear);
  }
  return Promise.reject(new Error(`No point-analysis provider configured for ${variableLabel}`));
}

export function analyzeSeries(series, variable, unit, datasetId, startYear, endYear) {
  return request("/analyze-series", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ series, variable, unit, dataset_id: datasetId, start_year: startYear, end_year: endYear }),
  });
}

export function getImpactExposure(bounds, signal) {
  const params = new URLSearchParams(Object.entries(bounds).map(([key, value]) => [key, String(value)]));
  return request(`/impact/exposure?${params}`, { signal });
}

export function analyzeSeaLevel(lat, lon, startYear, endYear) {
  return request("/analyze-sea-level", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, variable: "sea_level", start_year: startYear, end_year: endYear }),
  });
}

export function getSeaLevelAvailability(lat, lon) {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  return request(`/sea-level-availability?${params}`);
}

export function getCascadeCorrelation(lat, lon, variableALabel, variableBLabel, startYear, endYear) {
  const variable_a = LABEL_TO_ID[variableALabel];
  const variable_b = LABEL_TO_ID[variableBLabel];
  if (!variable_a || !variable_b) throw new Error("Unsupported cascade variable");
  return request("/cascade-correlation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, variable_a, variable_b, start_year: startYear, end_year: endYear }),
  });
}
