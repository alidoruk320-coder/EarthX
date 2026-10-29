import json
import logging
import math
import socket
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)

GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"
REQUEST_TIMEOUT_SECONDS = 8
CACHE_TTL_SECONDS = 6 * 60 * 60
CACHE_MAX_ENTRIES = 256
SPECIES_FACET_LIMIT = 10_000

# These GBIF backbone taxon keys were verified through the GBIF Species API.
CLASS_GROUPS = {
    "birds": 212,
    "mammals": 359,
    "reptiles": 358,
    "amphibians": 131,
    "fish": 204,
    "insects": 216,
}
THREAT_CATEGORIES = ("VU", "EN", "CR")

_cache: OrderedDict[tuple[float, float, float], tuple[float, dict]] = OrderedDict()
_cache_lock = threading.Lock()


def _build_region_params(lat: float, lon: float, radius_km: float) -> dict[str, str]:
    latitude_delta = radius_km / 111.32
    longitude_delta = radius_km / (
        111.32 * max(abs(math.cos(math.radians(lat))), 0.01)
    )
    south = max(-90.0, lat - latitude_delta)
    north = min(90.0, lat + latitude_delta)
    west = max(-180.0, lon - longitude_delta)
    east = min(180.0, lon + longitude_delta)
    return {
        "decimalLatitude": f"{south:.6f},{north:.6f}",
        "decimalLongitude": f"{west:.6f},{east:.6f}",
        "kingdomKey": "1",
        "limit": "0",
    }


def _fetch_gbif(params: dict[str, str | list[str]]) -> dict:
    url = f"{GBIF_OCCURRENCE_URL}?{urlencode(params, doseq=True)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "TwinEarth/1.0"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


def _facet_species_keys(params: dict[str, str]) -> tuple[set[int], bool]:
    query = {
        **params,
        "facet": "speciesKey",
        "facetLimit": str(SPECIES_FACET_LIMIT),
        "facetMincount": "1",
    }
    response = _fetch_gbif(query)
    facet_counts = next(
        (facet.get("counts", []) for facet in response.get("facets", [])
         if facet.get("field") == "SPECIES_KEY"),
        [],
    )
    keys = {
        int(item["name"])
        for item in facet_counts
        if str(item.get("name", "")).isdigit()
    }
    return keys, len(facet_counts) >= SPECIES_FACET_LIMIT


def _load_context(lat: float, lon: float, radius_km: float) -> dict:
    region_params = _build_region_params(lat, lon, radius_km)
    summary_params = {
        **region_params,
        "facet": ["speciesKey", "classKey"],
        "facetLimit": str(SPECIES_FACET_LIMIT),
        "facetMincount": "1",
    }
    with ThreadPoolExecutor(max_workers=4) as executor:
        summary_future = executor.submit(_fetch_gbif, summary_params)
        threat_futures = [
            executor.submit(
                _facet_species_keys,
                {
                    **region_params,
                    "iucnRedListCategory": category,
                    "facet": "speciesKey",
                    "facetLimit": str(SPECIES_FACET_LIMIT),
                    "facetMincount": "1",
                },
            )
            for category in THREAT_CATEGORIES
        ]
        summary = summary_future.result()
        threat_results = [future.result() for future in threat_futures]

    facets = {facet.get("field"): facet.get("counts", []) for facet in summary.get("facets", [])}
    species_facets = facets.get("SPECIES_KEY", [])
    species_count = len(species_facets)
    species_count_truncated = species_count >= SPECIES_FACET_LIMIT

    class_counts = {
        int(item["name"]): int(item["count"])
        for item in facets.get("CLASS_KEY", [])
        if str(item.get("name", "")).isdigit()
    }
    group_record_counts = {
        group: class_counts.get(class_key, 0)
        for group, class_key in CLASS_GROUPS.items()
    }
    classified_group_records = sum(class_counts.values())
    group_record_counts["other_or_unclassified"] = max(
        0,
        int(summary.get("count", 0)) - classified_group_records,
    )

    threatened_species: set[int] = set()
    threatened_species_truncated = any(is_truncated for _, is_truncated in threat_results)
    for species_keys, _ in threat_results:
        threatened_species.update(species_keys)

    return {
        "available": True,
        "lat": lat,
        "lon": lon,
        "radius_km": radius_km,
        "occurrence_records": int(summary.get("count", 0)),
        "species_count": species_count,
        "species_count_truncated": species_count_truncated,
        "group_record_counts": group_record_counts,
        "threatened_species_count": len(threatened_species),
        "threatened_species_count_truncated": threatened_species_truncated,
        "threat_categories": list(THREAT_CATEGORIES),
        "source": "GBIF occurrence API",
        "message": None,
    }


def get_biodiversity_context(lat: float, lon: float, radius_km: float) -> dict:
    rounded_lat = round(lat, 3)
    rounded_lon = round(lon, 3)
    rounded_radius = round(radius_km, 1)
    cache_key = (rounded_lat, rounded_lon, rounded_radius)

    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached:
            expires_at, result = cached
            if expires_at > time.monotonic():
                _cache.move_to_end(cache_key)
                return result
            del _cache[cache_key]

    try:
        result = _load_context(rounded_lat, rounded_lon, rounded_radius)
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, ValueError) as error:
        logger.warning(
            "GBIF biodiversity context request failed at %.3f, %.3f: %s",
            rounded_lat,
            rounded_lon,
            error,
        )
        return {
            "available": False,
            "lat": rounded_lat,
            "lon": rounded_lon,
            "radius_km": rounded_radius,
            "occurrence_records": None,
            "species_count": None,
            "species_count_truncated": False,
            "group_record_counts": None,
            "threatened_species_count": None,
            "threatened_species_count_truncated": False,
            "threat_categories": list(THREAT_CATEGORIES),
            "source": "GBIF occurrence API",
            "message": "Biyoçeşitlilik verisi şu anda alınamadı. Lütfen daha sonra tekrar deneyin.",
        }

    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, result)
        _cache.move_to_end(cache_key)
        while len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return result
