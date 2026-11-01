import test from "node:test";
import assert from "node:assert/strict";
import { getAnalysisPeriod, normalizeAnalysisRange } from "./analysisVariables.js";

test("analysis range defaults to the complete configured period", () => {
  const period = getAnalysisPeriod("GRACE Total Water Storage Anomaly");
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", period), period);
});

test("analysis range is clamped to product coverage and remains ordered", () => {
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", [2000, 2026]), [2003, 2016]);
  assert.deepEqual(normalizeAnalysisRange("GRACE Total Water Storage Anomaly", [2012, 2008]), [2012, 2012]);
});
