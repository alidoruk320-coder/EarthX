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

`vercel.json` builds and publishes `frontend/dist`; `api/generate-report.js` is the Gemini function and `api/[...path].js` proxies the app's allow-listed data API routes. The FastAPI service is still a separate backend and must be deployed to a Python host that supports Earth Engine. In Vercel project settings, set the server-only `EARTHVERSE_BACKEND_URL` to the backend's HTTPS origin (no `/api` suffix), and set `GEMINI_API_KEY` for report generation. The frontend uses same-origin `/api` requests through the proxy. In the backend environment, set `FRONTEND_ORIGINS` to the deployed Vercel origin and configure Earth Engine credentials (`GEE_SERVICE_ACCOUNT_EMAIL`, `GEE_PROJECT_ID`, and either `GEE_PRIVATE_KEY` or `GEE_PRIVATE_KEY_PATH`). For hosted backend secrets, `GEE_PRIVATE_KEY` can hold the private key with newline characters encoded as `\\n`. Without `EARTHVERSE_BACKEND_URL`, proxy routes return a clear 503 instead of the Vercel SPA fallback.

The Impact Mode and Global Story exposure panel use the backend `/api/impact/exposure` endpoint. It sums the 2020 WorldPop population grid within a selected place's bounding box and compares annual area-mean NASA VIIRS Black Marble radiance in 2014 and 2024; it is exposure context and does not establish environmental causality. This endpoint requires Earth Engine credentials. The Global Story page loads a country outline from Nominatim, runs annual trend statistics from the selected data source, and queries GBIF occurrence records separately.

Sea Level point analysis uses NASA/JPL's Sea Level Change Portal time-series service and requires the backend to be reachable, but no separate NASA API key is configured. It queries ocean grid cells around the selected coordinate; it does not return a value for inland points and is not a coastal tide-gauge record. The Sea Level Change Portal's downloadable datasets may require a free Earthdata account, but the integrated JPL statistics service is documented as an HTTP API. Sea-surface temperature remains a different variable.

The Global Story's “Regional contrast in sea level” demo requests both 1993–2007 annual series from the NASA/JPL endpoint at editable Atlantic and western Pacific ocean coordinates. It calculates Sen slope and Hamed–Rao modified Mann–Kendall significance live and displays the actual result returned by the service; it does not hard-code NASA article values. The NASA Earth Observatory article is contextual evidence for the historical regional pattern, not an exact validation of these particular 1-degree cells or this product version. A missing backend or unavailable ocean cell is surfaced as an error.

### Data notes

The globe uses Cesium ion aerial imagery for higher-detail satellite coverage when `VITE_CESIUM_TOKEN` is configured. If the token is absent or imagery cannot load, the app keeps a keyless NASA GIBS MODIS Terra true-color basemap, capped at zoom level 8; this lower-resolution fallback is intended for regional context, not house-level detail. The basemap capture date may differ from the selected analysis year. WebMercator does not cover the polar caps.

The selectable annual analysis series currently include NASA POWER daily 2 m temperature and corrected precipitation; MODIS Terra NDVI; SMAP L4 near-surface soil moisture; GRACE Tellus land total-water-storage anomaly; NASA/JPL ocean sea-surface-height anomaly; GPM IMERG monthly precipitation rate; merged TOMS/OMI total-column ozone; MERRA-2 2 m temperature, precipitable water, and evaporation; and GLDAS-2.1 Noah root-zone soil moisture and accumulated surface runoff. The products are fetched through their documented NASA/Google Earth Engine catalog entries or the NASA/JPL and NASA POWER services. Data cadence and product/band identifiers are shown in the analysis panel. The annual trend statistic uses a single backend Hamed–Rao modified Mann–Kendall test with Sen's slope. It requires at least eight annual observations and withholds significance if years are missing; annual aggregation reduces the seasonal cycle but does not remove all variability. Temperature and precipitation map rasters are separate MODIS/GPM visual products; their displayed point series come from NASA POWER. GPM is also available separately as a trend-analysis variable in mm/hr. GRACE Tellus V04 land grids end in January 2017, so the last complete annual observation is 2016. The sea-level series is a gridded ocean anomaly, not a coastal tide-gauge measurement. GLDAS runoff is modeled surface runoff, not measured river discharge. AIRS L3 is not integrated as a selectable series: the [NASA AIRS3STD V7 archive](https://disc.gsfc.nasa.gov/datasets/AIRS3STD_7.0/summary) is available through GES DISC, but its authenticated granule/subset access is not configured in this deployment. TOMS/MERGED_V4 is a merged TOMS/OMI record with interpolated dates, not an OMI-only series. Challenge mission names are examples, not a requirement to include every cited mission. Cascade results are lagged correlations with Bonferroni adjustment across tested lags, not proof of causation; serial autocorrelation is not modeled. Place-level region results currently average nine equally weighted sample points in the geocoder's bounding box, not an area-weighted boundary polygon.

NASA imagery acknowledgment: “We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).”
