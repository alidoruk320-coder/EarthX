const LAST_COMPLETE_YEAR = new Date().getUTCFullYear() - 1;

export const ANALYSIS_VARIABLES = {
  Temperature: {
    source: "NASA POWER",
    datasetId: "NASA POWER daily parameter T2M",
    unit: "°C (annual mean of daily values)",
    temporalResolution: "Daily; annual mean",
    startYear: 2002,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
    description: {
      en: "Annual mean 2 m air temperature from NASA POWER gridded daily estimates.",
      tr: "NASA POWER ızgaralı günlük tahminlerinden 2 m hava sıcaklığının yıllık ortalaması.",
    },
  },
  Precipitation: {
    source: "NASA POWER",
    datasetId: "NASA POWER daily parameter PRECTOTCORR",
    unit: "mm/day (annual mean)",
    temporalResolution: "Daily; annual mean rate",
    startYear: 2002,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://power.larc.nasa.gov/docs/services/api/temporal/daily/",
    description: {
      en: "Annual mean of NASA POWER corrected daily precipitation estimates; this is a daily rate, not annual accumulation.",
      tr: "NASA POWER düzeltilmiş günlük yağış tahminlerinin yıllık ortalaması; yıllık toplam değil günlük hızdır.",
    },
  },
  "NDVI / Vegetation": {
    source: "Google Earth Engine · NASA MODIS Terra",
    datasetId: "MODIS/061/MOD13Q1",
    unit: "NDVI index",
    temporalResolution: "16-day; annual mean",
    startYear: 2000,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1",
    description: {
      en: "A unitless MODIS vegetation greenness indicator using best-quality SummaryQA observations; it is not a direct count of plants or biomass.",
      tr: "En iyi kalite SummaryQA gözlemlerini kullanan boyutsuz MODIS bitki yeşilliği göstergesidir; doğrudan bitki veya biyokütle sayımı değildir.",
    },
  },
  "Soil Moisture": {
    source: "Google Earth Engine · NASA SMAP L4",
    datasetId: "NASA/SMAP/SPL4SMGP/008 · sm_surface",
    unit: "m³/m³ (0–5 cm surface layer)",
    temporalResolution: "3-hourly; annual mean",
    startYear: 2015,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008",
    description: {
      en: "SMAP L4 estimates near-surface soil water in the top 0–5 cm; the land product has no ocean values.",
      tr: "SMAP L4 üst 0–5 cm yüzeye yakın toprak suyunu tahmin eder; kara ürününde okyanus verisi yoktur.",
    },
  },
  "GRACE Total Water Storage Anomaly": {
    source: "Google Earth Engine · NASA GRACE/GRACE-FO",
    datasetId: "NASA/GRACE/MASS_GRIDS_V04/LAND · lwe_thickness_csr",
    unit: "cm water equivalent",
    temporalResolution: "Monthly; annual mean",
    startYear: 2003,
    endYear: 2016,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_LAND",
    description: {
      en: "Broad-scale terrestrial water-mass anomaly inferred from gravity; it does not isolate glaciers or groundwater.",
      tr: "Yerçekiminden çıkarılan geniş ölçekli kara su kütlesi anomalisidir; buzul veya yeraltı suyunu tek başına ayırmaz.",
    },
  },
  "Sea Level": {
    source: "NOAA CoastWatch blended satellite altimetry",
    datasetId: "noaacwBLENDEDsshDaily · sla",
    unit: "m sea-surface-height anomaly",
    temporalResolution: "Daily; annual mean",
    startYear: 2017,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://coastwatch.noaa.gov/erddap/info/noaacwBLENDEDsshDaily/index.html",
    description: {
      en: "Daily global 0.25° blended satellite-altimetry sea-surface-height anomaly; not a coastal tide-gauge or inland measurement. The current near-real-time product supports trend analysis from 2017.",
      tr: "Günlük küresel 0,25° birleştirilmiş uydu altimetrisi deniz yüzeyi yüksekliği anomalisidir; kıyı gelgit ölçeri veya kara ölçümü değildir. Güncel yakın-gerçek-zamanlı ürün trend analizini 2017'den başlatır.",
    },
  },
  "GPM Precipitation Rate": {
    source: "Google Earth Engine · NASA/JAXA GPM IMERG V07",
    datasetId: "NASA/GPM_L3/IMERG_MONTHLY_V07 · precipitation",
    unit: "mm/hr (annual mean rate)",
    temporalResolution: "Monthly; annual mean rate",
    startYear: 2000,
    endYear: 2024,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07",
    description: {
      en: "Monthly GPM IMERG precipitation-rate estimates averaged by year; it is not annual rainfall accumulation.",
      tr: "Aylık GPM IMERG yağış hızı tahminlerinin yıllık ortalamasıdır; yıllık yağış birikimi değildir.",
    },
  },
  "Total Column Ozone": {
    source: "Google Earth Engine · NASA TOMS/OMI merged product",
    datasetId: "TOMS/MERGED_V4 · ozone",
    unit: "Dobson units (DU)",
    temporalResolution: "Daily; annual mean",
    startYear: 1979,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/TOMS_MERGED_V4",
    description: {
      en: "Total ozone through the atmospheric column from the merged TOMS/OMI record; some missing dates are interpolated in the product.",
      tr: "Atmosfer sütunundaki toplam ozonu TOMS/OMI birleşik kaydından verir; üründe bazı eksik tarihler enterpole edilmiştir.",
    },
  },
  "MERRA-2 Air Temperature": {
    source: "Google Earth Engine · NASA MERRA-2 reanalysis",
    datasetId: "NASA/GSFC/MERRA/slv/2 · T2M",
    unit: "°C (annual mean of hourly values)",
    temporalResolution: "Hourly; annual mean",
    startYear: 1980,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_slv_2",
    description: {
      en: "MERRA-2 reanalysis of 2 m air temperature, converted from kelvin; a model-assimilation product, not a single satellite measurement.",
      tr: "MERRA-2 yeniden analizindeki 2 m hava sıcaklığı kelvinden çevrilir; tek uydu ölçümü değil, model ve veri asimilasyonu ürünüdür.",
    },
  },
  "MERRA-2 Evaporation Rate": {
    source: "Google Earth Engine · NASA MERRA-2 reanalysis",
    datasetId: "NASA/GSFC/MERRA/flx/2 · EVAP",
    unit: "mm/day (annual mean rate)",
    temporalResolution: "Hourly; annual mean rate",
    startYear: 1980,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_flx_2",
    description: {
      en: "MERRA-2 turbulent evaporation converted from kg/m²/s to mm/day; it is a reanalysis surface flux estimate.",
      tr: "MERRA-2 türbülans kaynaklı buharlaşma kg/m²/s biriminden mm/gün'e çevrilir; yeniden analiz yüzey akısı tahminidir.",
    },
  },
  "GLDAS Root-Zone Soil Moisture": {
    source: "Google Earth Engine · NASA GLDAS-2.1 Noah",
    datasetId: "NASA/GLDAS/V021/NOAH/G025/T3H · RootMoist_inst",
    unit: "kg/m² (annual mean water storage)",
    temporalResolution: "3-hourly; annual mean",
    startYear: 2000,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H",
    description: {
      en: "GLDAS model-estimated root-zone soil water storage; distinct from SMAP surface-layer soil moisture.",
      tr: "GLDAS modelinin kök bölgesi toprak suyu depolama tahminidir; SMAP yüzey toprağı neminden farklıdır.",
    },
  },
  "GLDAS Surface Runoff": {
    source: "Google Earth Engine · NASA GLDAS-2.1 Noah",
    datasetId: "NASA/GLDAS/V021/NOAH/G025/T3H · Qs_acc",
    unit: "mm water equivalent (annual total)",
    temporalResolution: "3-hourly; annual accumulation",
    startYear: 2000,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H",
    description: {
      en: "GLDAS model-estimated surface runoff accumulated across each year; it is not measured river discharge.",
      tr: "GLDAS modelinin yıllık biriktirilmiş yüzey akışı tahminidir; ölçülmüş nehir debisi değildir.",
    },
  },
};

export const ANALYSIS_VARIABLE_LABELS = Object.keys(ANALYSIS_VARIABLES);

export function getAnalysisPeriod(variable) {
  const definition = ANALYSIS_VARIABLES[variable];
  return definition ? [definition.startYear, definition.endYear] : [2002, LAST_COMPLETE_YEAR];
}

export function normalizeAnalysisRange(variable, range) {
  const [minimum, maximum] = getAnalysisPeriod(variable);
  const proposedStart = Number(range?.[0]);
  const proposedEnd = Number(range?.[1]);
  const start = Number.isFinite(proposedStart) ? Math.max(minimum, Math.min(maximum, Math.trunc(proposedStart))) : minimum;
  const end = Number.isFinite(proposedEnd) ? Math.max(start, Math.min(maximum, Math.trunc(proposedEnd))) : maximum;
  return [start, end];
}
