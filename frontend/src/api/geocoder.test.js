import assert from "node:assert/strict";
import test from "node:test";
import { isMarinePlace, resolvePlaceBoundary } from "./geocoder.js";

test("classifies Black Sea search results as marine even when class is absent", () => {
  assert.equal(isMarinePlace({
    class: null,
    category: "place",
    type: "sea",
    addresstype: "sea",
  }), true);
});

test("does not classify Turkey administrative search results as marine", () => {
  assert.equal(isMarinePlace({
    class: "boundary",
    category: "boundary",
    type: "administrative",
    addresstype: "country",
  }), false);
});

test("resolves an OSM relation Point to its polygon geometry", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({
    ok: true,
    json: async () => [{
      display_name: "Example area",
      geojson: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    }],
  });
  try {
    const result = await resolvePlaceBoundary({
      display_name: "Example area",
      class: "boundary",
      addresstype: "administrative",
      osm_type: "relation",
      osm_id: 7,
    });
    assert.equal(result.geojson.type, "Polygon");
    assert.equal(result.boundary_source, "OpenStreetMap/Nominatim object lookup");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("clearly marks a place when polygon and GAUL lookups fail", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) });
  try {
    const result = await resolvePlaceBoundary({
      display_name: "Example city",
      class: "place",
      addresstype: "city",
      lat: "1",
      lon: "2",
      boundingbox: ["0", "2", "1", "3"],
      osm_type: "node",
      osm_id: 8,
    });
    assert.equal(result.boundary_warning, "boundary_unavailable_bbox_fallback");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
