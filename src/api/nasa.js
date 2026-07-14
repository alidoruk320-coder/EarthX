const GIBS_BASE =
"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";

export function getSatelliteLayer(date) {

    return `${GIBS_BASE}/MODIS_Terra_CorrectedReflectance_TrueColor/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`;

}

export function getNDVILayer(date) {

    return `${GIBS_BASE}/MODIS_Terra_NDVI_8Day/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png`;

}

export function getLandSurfaceTemperature(date){

    return `${GIBS_BASE}/MODIS_Terra_Land_Surface_Temp_Day/default/${date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png`;

}