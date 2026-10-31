const BASE = "https://nominatim.openstreetmap.org";

const MARINE_TYPES = new Set([
    "sea",
    "ocean",
    "bay",
    "strait",
    "gulf",
    "channel",
    "sound",
    "fjord",
    "inlet",
    "estuary",
    "marine",
]);

export function isMarinePlace(place) {
    const values = [place?.class, place?.category, place?.type, place?.addresstype]
        .filter(Boolean)
        .map((value) => String(value).trim().toLowerCase());
    return values.some((value) => MARINE_TYPES.has(value));
}

const hasBoundary = (place) => ["Polygon", "MultiPolygon"].includes(place?.geojson?.type);

async function requestJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Search failed (${response.status})`);
    return response.json();
}

export async function searchPlace(text) {
    const query = new URLSearchParams({
        format: "jsonv2",
        q: text,
        limit: "5",
        polygon_geojson: "1",
        addressdetails: "1",
        extratags: "1",
    });
    const places = await requestJson(`${BASE}/search?${query}`);
    const polygonPlace = places.find(hasBoundary);
    if (polygonPlace) return [polygonPlace, ...places.filter((place) => place !== polygonPlace)];

    return places;
}

export async function resolvePlaceBoundary(place, searchText = "") {
    if (!place || hasBoundary(place)) return place;
    // Nominatim search can return a Point even when the matching OSM way or
    // relation has a usable boundary. Try that object before the GAUL fallback.
    const pointResult = place;
    if (pointResult?.osm_id && pointResult?.osm_type && pointResult.osm_type !== "node") {
        const prefix = pointResult.osm_type === "relation" ? "R" : "W";
        try {
            const lookup = new URLSearchParams({
                format: "jsonv2",
                osm_ids: `${prefix}${pointResult.osm_id}`,
                polygon_geojson: "1",
                addressdetails: "1",
            });
            const matches = await requestJson(`${BASE}/lookup?${lookup}`);
            const boundary = matches.find(hasBoundary);
            if (boundary) {
                return {
                    ...pointResult,
                    ...boundary,
                    boundary_source: "OpenStreetMap/Nominatim object lookup",
                };
            }
        } catch (error) {
            console.warn("OSM boundary lookup failed; keeping the search result:", error);
        }
    }

    // Use the free NASA/Google Earth Engine GAUL administrative boundary as
    // a final fallback for administrative places, when the app API is present.
    const adminResult = ["administrative", "boundary", "place"].includes(String(pointResult.class || "").toLowerCase())
        && ["country", "state", "province", "region", "county", "city", "town", "village", "municipality", "administrative"]
            .includes(String(pointResult.addresstype || "").toLowerCase());
    if (adminResult) {
        try {
            const params = new URLSearchParams({
                name: pointResult.name || searchText || pointResult.display_name,
                lat: pointResult.lat,
                lon: pointResult.lon,
                country_code: pointResult.address?.country_code || "",
                level: pointResult.addresstype === "country"
                    ? "0"
                    : ["city", "town", "village", "municipality", "suburb"].includes(pointResult.addresstype)
                        ? "2"
                        : "1",
            });
            const boundary = await requestJson(`/api/region-boundary?${params}`);
            if (hasBoundary({ geojson: boundary.geometry })) {
                return {
                    ...pointResult,
                    geojson: boundary.geometry,
                    boundingbox: boundary.boundingbox,
                    boundary_source: boundary.source,
                    boundary_type: boundary.region_type,
                };
            }
        } catch (error) {
            console.warn("Administrative boundary fallback failed:", error);
        }
    }

    return { ...pointResult, boundary_warning: "boundary_unavailable_bbox_fallback" };
}
