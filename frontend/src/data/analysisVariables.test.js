import test from "node:test";
import assert from "node:assert/strict";
import { ANALYSIS_VARIABLES, getAnalysisPeriod, normalizeAnalysisRange } from "./analysisVariables.js";

test("analysis range defaults to the complete configured period", () => {
  const period = getAnalysisPeriod("GRACE Total Water Storage Anomaly");
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", period), period);
});

test("analysis range is clamped to product coverage and remains ordered", () => {
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", [2000, 2026]), [2003, 2016]);
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", [2012, 2008]), [2012, 2012]);
});

test("fast MERRA-2 POWER products expose distinct variable names and units", () => {
  const temperature = ANALYSIS_VARIABLES["MERRA-2 Air Temperature"];
  const evapotranspiration = ANALYSIS_VARIABLES["MERRA-2 Evapotranspiration Energy Flux"];

  assert.equal(temperature.datasetId, "NASA POWER Monthly MERRA-2 · T2M");
  assert.equal(temperature.startYear, 1981);
  assert.equal(evapotranspiration.datasetId, "NASA POWER Monthly MERRA-2 · EVPTRNS");
  assert.match(evapotranspiration.unit, /MJ\/m²\/day/);
  assert.match(evapotranspiration.description.en, /not the same quantity as.*EVAP/);
  assert.equal(ANALYSIS_VARIABLES["MERRA-2 Evaporation Rate"], undefined);
});
