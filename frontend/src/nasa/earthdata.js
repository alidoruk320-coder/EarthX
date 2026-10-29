const GIBS_BASE = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const GIBS_CAPABILITIES_URL = `${GIBS_BASE}/wmts.cgi?SERVICE=WMTS&REQUEST=GetCapabilities`;
const CURRENT_YEAR = new Date().getUTCFullYear();
const LATEST_JULY_YEAR = new Date().getUTCMonth() >= 6 ? CURRENT_YEAR : CURRENT_YEAR - 1;

export const GIBS_LAYERS = {
  trueColor: {
    id: "MODIS_Terra_CorrectedReflectance_TrueColor",
    title: "True Color · MODIS Terra",
    category: "Land",
    format: "jpg",
    tileMatrixSet: "GoogleMapsCompatible_Level9",
    minYear: 2000,
    maxYear: LATEST_JULY_YEAR,
    alpha: 1,
  },
  ndvi: {
    id: "MODIS_Terra_L3_NDVI_Monthly",
    title: "Vegetation Index · MODIS Terra",
    category: "Biosphere",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level7",
    minYear: 2000,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.8,
  },
  landSurfaceTemp: {
    id: "MODIS_Terra_Land_Surface_Temp_Day",
    title: "Land Surface Temperature · Day",
    category: "Land",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level7",
    minYear: 2000,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.78,
  },
  snowCover: {
    id: "MODIS_Terra_L3_Snow_Cover_Monthly_Average_Pct",
    title: "Snow Cover · Monthly Average",
    category: "Cryosphere",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level6",
    minYear: 2000,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.82,
  },
  seaSurfaceTemp: {
    id: "GHRSST_L4_MUR_Sea_Surface_Temperature",
    title: "Sea Surface Temperature · MUR",
    category: "Ocean",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level7",
    minYear: 2002,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.8,
  },
  chlorophyll: {
    id: "MODIS_Aqua_L2_Chlorophyll_A",
    title: "Chlorophyll-a · MODIS Aqua",
    category: "Ocean",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level7",
    minYear: 2003,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.8,
  },
  precipitation: {
    id: "IMERG_Precipitation_Rate",
    title: "Precipitation Rate · IMERG",
    category: "Atmosphere",
    format: "png",
    tileMatrixSet: "GoogleMapsCompatible_Level6",
    minYear: 2000,
    maxYear: LATEST_JULY_YEAR,
    alpha: 0.8,
  },
};

export const GIBS_LAYER_FOR_VARIABLE = {
  "NDVI / Vegetation": "ndvi",
  Temperature: "landSurfaceTemp",
  Precipitation: "precipitation",
};

export const GIBS_GALLERY_KEYS = [
  "trueColor",
  "ndvi",
  "landSurfaceTemp",
  "snowCover",
  "seaSurfaceTemp",
  "chlorophyll",
  "precipitation",
];

let catalogPromise;

function textContent(parent, localName) {
  return [...parent.getElementsByTagNameNS("*", localName)]
    .map((node) => node.textContent?.trim())
    .find(Boolean) || "";
}

function parseYearRange(values, fallbackDate) {
  const years = `${values.join(" ")} ${fallbackDate}`.match(/\b(?:19|20)\d{2}\b/g) || [];
  return years.map(Number);
}

export async function fetchGibsCatalog() {
  if (!catalogPromise) {
    catalogPromise = fetch(GIBS_CAPABILITIES_URL)
      .then(async (response) => {
        if (!response.ok) throw new Error(`NASA GIBS catalog request failed (${response.status})`);
        const xml = new DOMParser().parseFromString(await response.text(), "application/xml");
        if (xml.querySelector("parsererror")) throw new Error("NASA GIBS returned an invalid WMTS catalog.");

        return [...xml.getElementsByTagNameNS("*", "Layer")].flatMap((node) => {
          const id = textContent(node, "Identifier");
          const title = textContent(node, "Title") || id;
          const abstract = textContent(node, "Abstract");
          const formats = [...node.getElementsByTagNameNS("*", "Format")].map((item) => item.textContent.trim());
          const format = formats.find((item) => item === "image/png" || item === "image/jpeg");
          const matrixSets = [...node.getElementsByTagNameNS("*", "TileMatrixSet")].map((item) => item.textContent.trim());
          const tileMatrixSet = matrixSets.find((item) => item.startsWith("GoogleMapsCompatible_Level"));
          const dimension = [...node.getElementsByTagNameNS("*", "Dimension")]
            .find((item) => textContent(item, "Identifier").toLowerCase() === "time");
          const dates = dimension
            ? [...dimension.getElementsByTagNameNS("*", "Value")].map((item) => item.textContent.trim())
            : [];
          const defaultDate = dimension ? textContent(dimension, "Default") : "";
          const resources = [...node.getElementsByTagNameNS("*", "ResourceURL")];
          const resource = resources.find((item) =>
            item.getAttribute("resourceType") === "tile"
            && item.getAttribute("format") === format
            && (item.getAttribute("template")?.includes("{TileMatrixSet}")
              || item.getAttribute("template")?.includes(`/${tileMatrixSet}/`))
            && (!dimension || item.getAttribute("template")?.includes("{Time}"))
          );
          if (!id || !format || !tileMatrixSet || !resource) return [];

          const years = parseYearRange(dates, defaultDate);
          const template = resource.getAttribute("template");
          return [{
            id,
            title,
            abstract,
            format: format === "image/jpeg" ? "jpeg" : "png",
            tileMatrixSet,
            template,
            defaultDate,
            minYear: years.length ? Math.min(...years) : CURRENT_YEAR,
            maxYear: years.length ? Math.min(LATEST_JULY_YEAR, Math.max(...years)) : LATEST_JULY_YEAR,
            temporal: Boolean(dimension),
            alpha: 0.8,
          }];
        });
      })
      .catch((error) => {
        catalogPromise = undefined;
        throw error;
      });
  }
  return catalogPromise;
}

export function registerGibsLayer(layer) {
  GIBS_LAYERS[layer.id] = layer;
  return layer.id;
}

export function getGibsDate(layerKey = "trueColor", year = null) {
  const layer = typeof layerKey === "string" ? GIBS_LAYERS[layerKey] : layerKey;
  if (!layer) throw new Error(`Unknown GIBS layer: ${layerKey}`);
  if (layer.temporal === false) return null;
  if (year == null) return layer.defaultDate || getLatestAvailableDate();
  const numericYear = Number(year);
  if (!Number.isInteger(numericYear) || numericYear < layer.minYear || numericYear > layer.maxYear) {
    throw new RangeError(`${layer.title} is available from ${layer.minYear} to ${layer.maxYear}.`);
  }
  return `${numericYear}-07-01`;
}

export function getGibsTileUrl(layerKey = "trueColor", year = null) {
  const layer = typeof layerKey === "string" ? GIBS_LAYERS[layerKey] : layerKey;
  if (!layer) throw new Error(`Unknown GIBS layer: ${layerKey}`);
  const template = layer.template || [
    GIBS_BASE,
    layer.id,
    "default",
    ...(layer.temporal === false ? [] : ["{Time}"]),
    layer.tileMatrixSet,
    "{TileMatrix}",
    "{TileRow}",
    "{TileCol}",
  ].join("/") + `.${layer.format}`;
  const date = getGibsDate(layer, year);
  return template
    .replaceAll("{Time}", date || "")
    .replaceAll("{TileMatrixSet}", layer.tileMatrixSet)
    .replaceAll("{TileMatrix}", "{z}")
    .replaceAll("{TileRow}", "{y}")
    .replaceAll("{TileCol}", "{x}");
}

export function getLatestAvailableDate() {
  const date = new Date();
  date.setDate(date.getDate() - 2);
  return date.toISOString().slice(0, 10);
}
