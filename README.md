EarthVerse
==========

EarthVerse is an interactive Earth-system trend investigation tool built for NASA Space Apps' “Be an Earth System Trend Detective” challenge. It connects regional NASA Earth-observation and model time series with annual visualizations, Sen's slope, and Hamed–Rao modified Mann–Kendall analysis so users can ask what is changing, where, how quickly, and with what statistical evidence.

The project combines a React/Cesium interface, NASA GIBS imagery, NASA POWER and NASA/JPL services, Google Earth Engine datasets, and a FastAPI data backend. Imagery is visual context; numerical trend results come from the explicitly identified analysis source shown in the interface.

See [SUBMISSION_BRIEF.md](SUBMISSION_BRIEF.md) for the challenge mapping, concise demo script, scientific limitations, and deployment/submission release checklist.

## Project structure

EarthVerse-AI/
├── frontend/                 # React + Cesium + Vite application
│   ├── public/
│   ├── src/
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── backend/                  # FastAPI + Earth Engine services
│   ├── app/
│   ├── requirements.txt
│   └── .env.example
├── api/                      # Vercel serverless functions
├── .env.example              # Frontend Vite variables; .env remains at root
├── package.json              # Workspace and root convenience commands
└── README.md
## Run locally

Clone the repository and install the dependencies:

git clone <repository-url>
cd EarthVerse-AI
npm install
Start the frontend development server:

npm run dev
The application will be available at the local address shown by Vite.

## Frontend and backend

The repository is organized as an npm workspace: React/Cesium lives in `frontend/`, FastAPI and Google Earth Engine live in `backend/`, and the Gemini proxy lives in `api/` as a Vercel serverless function. The root `.env` is preserved and Vite reads it through the frontend config's `envDir`.

### Run the frontend

```sh
npm install
npm run dev
```

### Run the backend

Use Python 3.12. Create a backend-local environment file from the template and add a Google Earth Engine service account key:

```sh
cp backend/.env.example backend/.env
npm run backend:install
```

Set `GEE_SERVICE_ACCOUNT_EMAIL`, `GEE_PRIVATE_KEY_PATH`, and `GEE_PROJECT_ID` in `backend/.env`. Keep the private key file out of version control. Then start the API:

```sh
npm run backend:dev
```

The root commands are workspace shortcuts: `npm run frontend:dev` and `npm run frontend:build` target the frontend explicitly; `npm run dev` and `npm run build` remain convenient defaults. Vite proxies `/api` requests to `http://127.0.0.1:8000`. Check backend availability at `/api/health`; it reports `gee_ready: false` until valid Earth Engine credentials are configured. Without GEE credentials the frontend remains usable, while GEE-dependent endpoints return HTTP 503 instead of fabricated data.

### Vercel deployment

`vercel.json` configures one Vercel Services deployment with a Vite frontend and FastAPI backend. `/api/generate-report` is served by `frontend/api/generate-report.js`; other `/api/*` requests go directly to FastAPI. No separate backend host or `EARTHVERSE_BACKEND_URL` is needed. The FastAPI service uses Python 3.12 as pinned in `backend/.python-version`.

Before deploying, import this repository into Vercel and add these environment variables to the project:

- `GEE_SERVICE_ACCOUNT_EMAIL`, `GEE_PROJECT_ID`, and `GEE_PRIVATE_KEY` for the backend. Store the service-account private key as a Vercel secret; if its newlines must be escaped, use literal `\\n`. Do not upload `gee-service-account.json` or set `GEE_PRIVATE_KEY_PATH` in Vercel.
- `GEMINI_API_KEY` for the server-side report function.
- `VITE_CESIUM_TOKEN` is optional and is used at frontend build time for higher-detail Cesium ion imagery. Without it, the NASA GIBS basemap remains available.
- `FRONTEND_ORIGINS` may be set to the deployed site origin; same-origin frontend requests do not require cross-origin access.

Set the variables for Preview and Production as appropriate, then deploy a Preview first. Verify `/api/health` reports `status: "ok"` and `gee_ready: true`, then test a point query, boundary/region request, SWOT, sea-level availability, and report generation before promoting to Production. FastAPI endpoints run as Vercel Functions and are subject to Vercel's function duration and usage limits; long regional analyses may need smaller areas or a different compute host if they exceed those limits. Services availability, Hobby plan quotas, and non-commercial-use restrictions should be checked against the current Vercel plan before making the site public.

The Impact Mode and Global Story exposure panel use the backend `/api/impact/exposure` endpoint. It sums the 2020 WorldPop population grid within a selected place's bounding box and compares annual area-mean NASA VIIRS Black Marble radiance in 2014 and 2024; it is exposure context and does not establish environmental causality. This endpoint requires Earth Engine credentials. The Global Story page loads a country outline from Nominatim, runs annual trend statistics from the selected data source, and queries GBIF occurrence records separately.

Sea Level point analysis uses NASA/JPL's Sea Level Change Portal time-series service and requires the backend to be reachable, but no separate NASA API key is configured. It queries ocean grid cells around the selected coordinate; it does not return a value for inland points and is not a coastal tide-gauge record. The Sea Level Change Portal's downloadable datasets may require a free Earthdata account, but the integrated JPL statistics service is documented as an HTTP API. Sea-surface temperature remains a different variable.

The Global Story's “Regional contrast in sea level” demo requests both 1993–2007 annual series from the NASA/JPL endpoint at editable Atlantic and western Pacific ocean coordinates. It calculates Sen slope and Hamed–Rao modified Mann–Kendall significance live and displays the actual result returned by the service; it does not hard-code NASA article values. The NASA Earth Observatory article is contextual evidence for the historical regional pattern, not an exact validation of these particular 1-degree cells or this product version. A missing backend or unavailable ocean cell is surfaced as an error.

### Data notes

The globe uses Cesium ion aerial imagery for higher-detail satellite coverage when `VITE_CESIUM_TOKEN` is configured. If the token is absent or imagery cannot load, the app keeps a keyless NASA GIBS MODIS Terra true-color basemap, capped at zoom level 8; this lower-resolution fallback is intended for regional context, not house-level detail. The basemap capture date may differ from the selected analysis year. WebMercator does not cover the polar caps.

The selectable annual analysis series currently include NASA POWER daily 2 m temperature and corrected precipitation; MODIS Terra NDVI; SMAP L4 near-surface soil moisture; GRACE Tellus land total-water-storage anomaly; NASA/JPL ocean sea-surface-height anomaly; GPM IMERG monthly precipitation rate; TOMS/MERGED_V4 total-column ozone; and NASA POWER monthly MERRA-2 2 m temperature and evapotranspiration energy flux. In the Earth Engine collection currently queried by the app, ozone observations begin in October 2004, so trend analyses use complete years from 2005 onward; its daily pixels are averaged directly into annual composites. GLDAS root-zone soil moisture and surface runoff have been removed from the analysis catalog: the regional quick path only used a few sample points and could not support a sufficiently representative regional estimate. The MERRA-2 POWER series use one multi-year monthly API request per sample point rather than sequential yearly Earth Engine requests. POWER's `EVPTRNS` API reports kWh/m²/day and the app converts it to the documented MJ/m²/day; this energy-flux product is not the same quantity as the GEE MERRA-2 `EVAP` turbulent mass flux. Its distinct name and unit are shown explicitly. The remaining products are fetched through their documented NASA/Google Earth Engine catalog entries or the NASA/JPL and NASA POWER services. Data cadence and product/band identifiers are shown in the analysis panel. The annual trend statistic uses a single backend Hamed–Rao modified Mann–Kendall test with Sen's slope. It requires at least eight annual observations and withholds significance if years are missing; annual aggregation reduces the seasonal cycle but does not remove all variability. Temperature and precipitation map rasters are separate MODIS/GPM visual products; their displayed point series come from NASA POWER. GPM is also available separately as a trend-analysis variable in mm/hr. GRACE Tellus V04 land grids end in January 2017, so the last complete annual observation is 2016. The sea-level series is a gridded ocean anomaly, not a coastal tide-gauge measurement. AIRS L3 is not integrated as a selectable series: the [NASA AIRS3STD V7 archive](https://disc.gsfc.nasa.gov/datasets/AIRS3STD_7.0/summary) is available through GES DISC, but its authenticated granule/subset access is not configured in this deployment. TOMS/MERGED_V4 is a merged TOMS/OMI record with interpolated dates, not an OMI-only series. Challenge mission names are examples, not a requirement to include every cited mission. Cascade results are lagged correlations with Bonferroni adjustment across tested lags, not proof of causation; serial autocorrelation is not modeled. Search first uses Nominatim administrative polygons, then attempts the corresponding OSM object, then a FAO GAUL boundary fallback for administrative results. The Earth Engine fallback prefers `FAO/GAUL/2025/level1` and `level2` where available; country boundaries and compatibility fallbacks use the 2015 level0, detailed, or simplified collections. GeometryCollections returned by boundary sources are reduced to their Polygon/MultiPolygon members before analysis. If no polygon source is available, the app states that it is using a bounding-box sample and not a polygon mean. Fast estimates use a boundary-filtered sample of at most 16 points (some high-volume products intentionally reduce the count further); the panel reports the actual count. Use polygon mode for the full area-weighted polygon analysis when available for that product.

### SWOT LakeSP observations

The separate SWOT mode uses NASA PO.DAAC Hydrocron's public `SWOT_L2_HR_LakeSP_D` LakeSP series for two verified features only: Large Aral Sea (`PriorLake` ID `4610055052`) and Lake Chad (`PriorLake` ID `1620031382`). A clicked coordinate selects the nearest supported feature within 200 km; returned observations describe the lake feature, not the exact clicked point. The current checked-in cache contains 233 valid Large Aral Sea and 107 valid Lake Chad observations, fetched on 2026-11-13. The interface plots individual irregular overpasses as points—never annual averages—and overlays an exploratory Theil–Sen slope calculated using the actual elapsed time between observations. This descriptive slope uses the observations as cached, with quality/ice flags exposed but not filtered; it is not an inferential trend test. The app does not report Mann–Kendall, a p-value, or statistical significance for SWOT. These lake observations are water-surface elevation, not direct storage volume or river discharge.

Refresh the public cache before a release or as part of a scheduled maintenance job; the updater validates the response and replaces the file atomically, retaining the existing cache if a request fails:

```sh
cd backend
python scripts/refresh_swot_lake_cache.py
```

The backend needs outbound HTTPS access to Hydrocron when refreshing. Runtime analyses read the checked-in cache and do not depend on Hydrocron availability. See the [NASA PO.DAAC Hydrocron documentation](https://podaac.github.io/hydrocron/).

NASA imagery acknowledgment: “We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).”
