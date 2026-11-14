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
    startYear: 2005,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://developers.google.com/earth-engine/datasets/catalog/TOMS_MERGED_V4",
    description: {
      en: "Annual mean total-column ozone from TOMS/MERGED_V4 as currently available in Earth Engine; the complete annual record starts in 2005. Source dates may include interpolated values.",
      tr: "Google Earth Engine'de mevcut TOMS/MERGED_V4 koleksiyonundan yıllık ortalama toplam sütun ozonu; tam yıllık kayıt 2005'te başlar. Kaynakta enterpole edilmiş tarihler bulunabilir.",
    },
  },
  "MERRA-2 Air Temperature": {
    source: "NASA POWER · NASA MERRA-2",
    datasetId: "NASA POWER Monthly MERRA-2 · T2M",
    unit: "°C (annual mean)",
    temporalResolution: "Monthly; annual mean",
    startYear: 1981,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/",
    description: {
      en: "Monthly NASA POWER 2 m air temperature derived from the MERRA-2 meteorological record; annual values use the API's annual aggregate.",
      tr: "MERRA-2 meteoroloji kaydından türetilen NASA POWER aylık 2 m hava sıcaklığıdır; yıllık değerlerde API'nin yıllık agregası kullanılır.",
    },
  },
  "MERRA-2 Evapotranspiration Energy Flux": {
    source: "NASA POWER · NASA MERRA-2",
    datasetId: "NASA POWER Monthly MERRA-2 · EVPTRNS",
    unit: "MJ/m²/day (annual mean)",
    temporalResolution: "Monthly; annual mean energy flux",
    startYear: 1981,
    endYear: LAST_COMPLETE_YEAR,
    sourceUrl: "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/",
    description: {
      en: "NASA POWER EVPTRNS is MERRA-2-derived evapotranspiration energy flux. POWER's API reports kWh/m²/day; values are converted to the documented MJ/m²/day unit. This is not the same quantity as the GEE MERRA-2 EVAP turbulent mass flux.",
      tr: "NASA POWER EVPTRNS, MERRA-2 kaynaklı evapotranspirasyon enerji akısıdır. POWER API'si kWh/m²/gün döndürür; değerler belgelenen MJ/m²/gün birimine çevrilir. Bu, GEE MERRA-2 EVAP türbülans kaynaklı kütle akısıyla aynı ölçüm değildir.",
    },
  },
  "SWOT Lake Surface Water Elevation": {
    source: "NASA PO.DAAC Hydrocron · SWOT",
    datasetId: "SWOT_L2_HR_LakeSP_D · PriorLake",
    unit: "m (WGS84 ellipsoidal water-surface elevation)",
    temporalResolution: "Irregular SWOT satellite overpasses (nominal 21-day repeat)",
    startYear: 2023,
    endYear: new Date().getUTCFullYear(),
    sourceUrl: "https://podaac.github.io/hydrocron/",
    description: {
      en: "SWOT LakeSP water-surface elevation observations for the verified Large Aral Sea and Lake Chad lake features. Coordinates select the nearest supported lake; observations are irregular and are shown without a long-term trend or significance test.",
      tr: "Doğrulanmış Büyük Aral Gölü ve Çad Gölü özellikleri için SWOT LakeSP su yüzeyi yüksekliği gözlemleri. Koordinat en yakın desteklenen gölü seçer; düzensiz gözlemler uzun dönem trend veya anlamlılık testi yapılmadan gösterilir.",
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
