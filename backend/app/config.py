import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

GEE_SERVICE_ACCOUNT_EMAIL = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
GEE_PRIVATE_KEY_PATH = os.getenv("GEE_PRIVATE_KEY_PATH")
GEE_PRIVATE_KEY = os.getenv("GEE_PRIVATE_KEY")
GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID")
CURRENT_COMPLETE_YEAR = datetime.now(timezone.utc).year - 1
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")).split(",")
    if origin.strip()
]

# Frontend'deki "Temperature", "NDVI / Vegetation" gibi etiketleri
# backend değişken kimliklerine eşliyoruz. Earth.jsx'teki VARIABLES
# listesiyle senkron tutulmalı.
LABEL_TO_ID = {
    "Temperature": "temperature",
    "NDVI / Vegetation": "ndvi",
    "GRACE Total Water Storage Anomaly": "grace_tws",
    "Soil Moisture": "soil_moisture",
    "Precipitation": "precipitation",
    "GPM Precipitation Rate": "gpm_precipitation",
    "Total Column Ozone": "total_column_ozone",
    "MERRA-2 Air Temperature": "merra2_t2m",
    "MERRA-2 Precipitable Water": "merra2_precipitable_water",
    "MERRA-2 Evaporation Rate": "merra2_evaporation",
    "GLDAS Root-Zone Soil Moisture": "gldas_root_moisture",
    "GLDAS Surface Runoff": "gldas_surface_runoff",
}

VARIABLES = {
    "temperature": {
        "collection": "MODIS/061/MOD11A2",
        "band": "LST_Day_1km",
        "equal_area": True,
        "scale_factor": 0.02,
        "offset": -273.15,   # Kelvin -> Celsius
        "palette": ["040274", "0502a3", "241fa8", "1e5cc4", "1b8dd1",
                    "04b2ea", "30d3f5", "89f2ff", "ffffff", "ffe700",
                    "ffb100", "ff7a00", "ff3300", "c40000", "7a0000"],
        "vis_min": -10, "vis_max": 45, "unit": "°C",
        "scale_meters": 5000,
        "quality_band": "QC_Day",
        "start_year": 2000, "latest_complete_year": CURRENT_COMPLETE_YEAR,
    },
    "ndvi": {
        "collection": "MODIS/061/MOD13Q1",
        "band": "NDVI",
        "equal_area": True,
        "scale_factor": 0.0001,
        "offset": 0,
        "palette": ["ff3300", "ff8c00", "ffd700", "a3c400", "5a9216", "2e6b0f"],
        "vis_min": 0, "vis_max": 1, "unit": "NDVI index",
        "scale_meters": 250,
        "quality_band": "SummaryQA",
        "start_year": 2000, "first_full_year": 2001,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "large_region": {
            "area_threshold_m2": 100_000_000_000,
            "collection": "MODIS/061/MOD13A3",
            "band": "NDVI",
            "scale_meters": 1000,
            "quality_band": "SummaryQA",
            "temporal_resolution": "Monthly",
        },
    },
    "grace_tws": {
        "collection": "NASA/GRACE/MASS_GRIDS_V04/LAND",
        "band": "lwe_thickness_csr",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["8b0000", "ff4500", "ffff99", "87ceeb", "1e90ff", "00008b"],
        "vis_min": -20, "vis_max": 20, "unit": "cm su eşdeğeri",
        "scale_meters": 100000,
        "start_year": 2003, "latest_complete_year": 2016,
    },
    "soil_moisture": {
        "collection": "NASA/SMAP/SPL4SMGP/008",
        "band": "sm_surface",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["8b4513", "d2b48c", "f0e68c", "90ee90", "228b22", "006400"],
        "vis_min": 0, "vis_max": 0.5, "unit": "m³/m³",
        "scale_meters": 11000,
        "start_year": 2015, "latest_complete_year": CURRENT_COMPLETE_YEAR,
    },
    "precipitation": {
        "collection": "NASA/GPM_L3/IMERG_MONTHLY_V07",
        "band": "precipitation",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["ffffff", "a6d9f7", "67a9cf", "2166ac", "08306b"],
        "vis_min": 0, "vis_max": 1.5, "unit": "mm/hr (annual mean rate)",
        "scale_meters": 11132,
        "start_year": 2000,
        "first_full_year": 2001,
        "latest_complete_year": 2024,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07",
        "aggregation": "mean",
        "temporal_resolution": "Monthly",
    },
    "total_column_ozone": {
        "collection": "TOMS/MERGED_V4",
        "band": "ozone",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["5e4fa2", "3288bd", "66c2a5", "abdda4", "e6f598", "ffffbf", "fee08b", "fdae61", "f46d43", "d53e4f", "9e0142"],
        "vis_min": 180, "vis_max": 500, "unit": "Dobson units (DU)",
        "scale_meters": 111000,
        "start_year": 1979,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/TOMS_MERGED_V4",
        "aggregation": "mean",
        "temporal_resolution": "Daily",
        "source": "NASA TOMS/OMI merged product; interpolated dates occur in the source record",
    },
    "merra2_t2m": {
        "collection": "NASA/GSFC/MERRA/slv/2",
        "band": "T2M",
        "equal_area": False,
        "scale_factor": 1, "offset": -273.15,
        "palette": ["313695", "4575b4", "74add1", "abd9e9", "e0f3f8", "ffffbf", "fee090", "fdae61", "f46d43", "d73027", "a50026"],
        "vis_min": -40, "vis_max": 45, "unit": "°C (annual mean of hourly values)",
        "scale_meters": 55000,
        "start_year": 1980,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_slv_2",
        "aggregation": "mean",
        "temporal_resolution": "Hourly",
        "source": "NASA MERRA-2 atmospheric reanalysis",
    },
    "merra2_precipitable_water": {
        "collection": "NASA/GSFC/MERRA/slv/2",
        "band": "TQV",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["fff7ec", "fee8c8", "fdd49e", "fdbb84", "fc8d59", "ef6548", "d7301f", "990000"],
        "vis_min": 0, "vis_max": 70, "unit": "kg/m² (annual mean)",
        "scale_meters": 55000,
        "start_year": 1980,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_slv_2",
        "aggregation": "mean",
        "temporal_resolution": "Hourly",
        "source": "NASA MERRA-2 atmospheric reanalysis",
    },
    "merra2_evaporation": {
        "collection": "NASA/GSFC/MERRA/flx/2",
        "band": "EVAP",
        "equal_area": False,
        "scale_factor": 86400, "offset": 0,
        "palette": ["fff7bc", "c7e9b4", "7fcdbb", "41b6c4", "2c7fb8", "253494"],
        "vis_min": 0, "vis_max": 8, "unit": "mm/day (annual mean rate)",
        "scale_meters": 55000,
        "start_year": 1980,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GSFC_MERRA_flx_2",
        "aggregation": "mean",
        "temporal_resolution": "Hourly",
        "source": "NASA MERRA-2 turbulent evaporation; kg/m²/s converted to mm/day",
    },
    "gldas_root_moisture": {
        "collection": "NASA/GLDAS/V021/NOAH/G025/T3H",
        "band": "RootMoist_inst",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["8c510a", "d8b365", "f6e8c3", "c7eae5", "5ab4ac", "01665e"],
        "vis_min": 0, "vis_max": 500, "unit": "kg/m² (annual mean water storage)",
        "scale_meters": 27830,
        "start_year": 2000,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H",
        "aggregation": "mean",
        "temporal_resolution": "3-hourly",
        "source": "NASA GLDAS-2.1 Noah land-surface model",
    },
    "gldas_surface_runoff": {
        "collection": "NASA/GLDAS/V021/NOAH/G025/T3H",
        "band": "Qs_acc",
        "equal_area": False,
        "scale_factor": 1, "offset": 0,
        "palette": ["ffffcc", "c2e699", "78c679", "31a354", "006837"],
        "vis_min": 0, "vis_max": 1500, "unit": "mm water equivalent (annual total)",
        "scale_meters": 27830,
        "start_year": 2000,
        "latest_complete_year": CURRENT_COMPLETE_YEAR,
        "documentation_url": "https://developers.google.com/earth-engine/datasets/catalog/NASA_GLDAS_V021_NOAH_G025_T3H",
        "aggregation": "sum",
        "temporal_resolution": "3-hourly accumulations summed to annual total",
        "source": "NASA GLDAS-2.1 Noah land-surface model; modeled surface runoff, not measured river discharge",
    },
}

# The map's legacy "Precipitation" id and the explicitly named GPM analysis
# variable use the same IMERG monthly-rate product and processing settings.
VARIABLES["gpm_precipitation"] = VARIABLES["precipitation"]

# Dedicated configuration for the ten Earth Engine variables that support
# polygon-wide, pixel-area-weighted annual aggregation. Quality masks are
# expressed as a band and accepted bit values; MODIS SummaryQA=0 is best quality.
_REGION_VARIABLES = (
    "ndvi",
    "soil_moisture",
    "grace_tws",
    "gpm_precipitation",
    "total_column_ozone",
    "merra2_t2m",
    "merra2_precipitable_water",
    "merra2_evaporation",
    "gldas_root_moisture",
    "gldas_surface_runoff",
)
region_config = {
    variable_id: {
        "variable_id": variable_id,
        "collection": VARIABLES[variable_id]["collection"],
        "band": VARIABLES[variable_id]["band"],
        "scale": VARIABLES[variable_id].get(
            "native_scale_meters",
            VARIABLES[variable_id]["scale_meters"],
        ),
        "equal_area": VARIABLES[variable_id]["equal_area"],
        "nominal_cell_area_m2": VARIABLES[variable_id].get(
            "native_scale_meters",
            VARIABLES[variable_id]["scale_meters"],
        ) ** 2,
        "large_region": VARIABLES[variable_id].get("large_region"),
        "aggregate": VARIABLES[variable_id].get("aggregation", "mean"),
        "monthly_first": variable_id in {
            "soil_moisture",
            "merra2_t2m",
            "merra2_precipitable_water",
            "merra2_evaporation",
            "gldas_root_moisture",
            "gldas_surface_runoff",
        },
        "mask": (
            {"band": VARIABLES[variable_id]["quality_band"], "accepted_values": [0]}
            if VARIABLES[variable_id].get("quality_band")
            else None
        ),
        "scale_factor": VARIABLES[variable_id]["scale_factor"],
        "offset": VARIABLES[variable_id].get("offset", 0),
        "unit": VARIABLES[variable_id]["unit"],
        "start_year": VARIABLES[variable_id]["start_year"],
        "first_full_year": VARIABLES[variable_id].get(
            "first_full_year", VARIABLES[variable_id]["start_year"]
        ),
        "latest_complete_year": VARIABLES[variable_id]["latest_complete_year"],
        "documentation_url": VARIABLES[variable_id].get("documentation_url"),
        "temporal_resolution": VARIABLES[variable_id].get("temporal_resolution"),
        "source": VARIABLES[variable_id].get("source"),
    }
    for variable_id in _REGION_VARIABLES
}
