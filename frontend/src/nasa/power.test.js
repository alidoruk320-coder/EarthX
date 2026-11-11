import test from "node:test";
import assert from "node:assert/strict";
import { getNasaPowerSeries } from "./power.js";

test("MERRA-2 POWER monthly series uses the annual API aggregates", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  let requestedUrl;

  globalThis.fetch = async (url, options) => {
    requestedUrl = new URL(url);
    assert.ok(options.signal instanceof AbortSignal);
    return {
      ok: true,
      json: async () => ({
        properties: {
          parameter: {
            T2M: {
              "202013": 5.5,
              ...Object.fromEntries(Array.from({ length: 12 }, (_, index) => [
                `2021${String(index + 1).padStart(2, "0")}`,
                7,
              ])),
            },
          },
        },
      }),
    };
  };

  const series = await getNasaPowerSeries(41, 29, "MERRA-2 Air Temperature", 2020, 2021);

  assert.equal(requestedUrl.pathname, "/api/temporal/monthly/point");
  assert.equal(requestedUrl.searchParams.get("parameters"), "T2M");
  assert.equal(requestedUrl.searchParams.get("community"), "RE");
  assert.equal(requestedUrl.searchParams.get("start"), "2020");
  assert.equal(requestedUrl.searchParams.get("end"), "2021");
  assert.deepEqual(series, [
    { year: 2020, value: 5.5 },
    { year: 2021, value: 7 },
  ]);
});

test("POWER evapotranspiration energy flux retains its published annual value", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  let requestedUrl;

  globalThis.fetch = async (url) => {
    requestedUrl = new URL(url);
    return {
      ok: true,
      json: async () => ({
        properties: { parameter: { EVPTRNS: { "202513": 0.1385 } } },
      }),
    };
  };

  const series = await getNasaPowerSeries(
    41, 29, "MERRA-2 Evapotranspiration Energy Flux", 2025, 2025,
  );

  assert.equal(requestedUrl.searchParams.get("parameters"), "EVPTRNS");
  assert.equal(requestedUrl.searchParams.get("community"), "RE");
  assert.deepEqual(series, [{ year: 2025, value: 0.499 }]);
});
