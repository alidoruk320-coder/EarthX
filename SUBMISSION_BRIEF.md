# EarthVerse — Judge Brief

## One-sentence pitch

EarthVerse turns NASA Earth-observation and model data into an interactive trend investigation: choose a place and variable, inspect its annual record, estimate the rate with Sen's slope, and evaluate monotonic-trend evidence with an autocorrelation-adjusted Mann–Kendall test.

## The challenge response

The app covers the challenge's core workflow:

1. **Choose a measurable Earth-system variable.** The analysis catalog describes each product, band, unit, temporal cadence, period, and source. Available examples include NASA POWER, MODIS, SMAP, GRACE/GRACE-FO, GPM IMERG, MERRA-2, a merged TOMS/OMI ozone record, and NASA/JPL sea-level anomaly.
2. **Choose a place or coordinate.** Point analysis requests data at the chosen coordinate. Search prefers an administrative polygon, tries the matching OSM object if search returns a Point, and then tries a FAO GAUL administrative boundary. If no polygon is available, the panel explicitly labels the bounding-box fallback. Fast mode is a sampled estimate; polygon mode performs the area-weighted GEE reduction where supported.
3. **Inspect the time series.** Trend products are aggregated to annual values and shown with their selected period and units. The separate SWOT mode shows individual, irregular lake overpasses instead of annualizing them. Product cadence is disclosed so averages are not mistaken for totals.
4. **Assess the trend where appropriate.** Annual trend products report Sen's slope and Hamed–Rao modified Mann–Kendall results. The test requires at least eight continuous annual observations and withholds significance when years are missing. SWOT LakeSP is explicitly descriptive only: its short, irregular observations receive no trend test or p-value. A non-significant result is reported as inconclusive evidence, not proof of no change.

## Suggested live demo (about 3 minutes)

1. Search for a country or region and verify the displayed boundary source/type. Explain the distinction between fast sampled estimates and area-weighted polygon analysis; the panel shows the method and actual sample or valid-pixel counts.
2. Select a variable with a clearly documented product and cadence. Show the source, unit, annual chart, observation count, Sen slope, p-value, and significance interpretation together.
3. Open **Global Story** and compare baseline imagery with the selected year. Point out that imagery is visual context; the numerical trend comes from the named analysis dataset.
4. Open **Regional contrast in sea level**. Run both live NASA/JPL series and let the returned slopes and p-values determine whether this pair actually demonstrates opposite directions. Do not claim significance if either p-value is at least 0.05 or unavailable.
5. Close with the data-source links and a limitation: opposite spatial trends can motivate process questions, but this tool does not establish causation.

## Scientific scope and honest limitations

- The NASA Earth Observatory 1993–2007 sea-level map is contextual background for the demo. It is not a validation of the exact two 1-degree cells returned by the live service. Only call this a verified opposite-trend case after comparing the displayed cell series/statistics with an independent product or published regional analysis.
- AIRS L3 is not currently a selectable analysis source. Its absence does not omit a mandatory challenge objective: the challenge lists missions and models as examples. Do not imply AIRS is integrated.
- TOMS/OMI is the merged TOMS/OMI product, not an OMI-only record.
- GLDAS root-zone moisture and surface runoff were removed from the selectable analysis catalog because the regional quick path relied on only a few points and could not support a representative regional estimate.
- SWOT LakeSP is available only for the verified Large Aral Sea and Lake Chad features in the cached series. A selected coordinate identifies a nearby lake feature; it is not the measurement location. The plotted dots are irregular water-surface-elevation overpasses, not annual values; the dashed Theil–Sen slope is a descriptive summary over actual elapsed dates, not a significance test. No p-value or statistical significance is claimed. Quality and ice flags are exposed but not filtered until their definitions are validated for the product version.
- NASA POWER temperature and precipitation point series are separate from the MODIS/GPM rendered map layers. The interface should keep this distinction visible.
- The trend map shows annual slope/ranking, not pixel-level significance. Point-series significance must not be inferred from map colors.
- The timeline year selects imagery. Trend statistics use the complete annual time series and therefore remain the same when only the imagery year changes.
- Annual aggregation reduces seasonal variation but is not a full seasonal-cycle removal or a causal attribution analysis.
- Sea-level anomaly is an ocean-grid measurement, not a coastal tide-gauge or inland measurement. GRACE V04 land data end in 2016; each product has its own temporal coverage.
- Live NASA, Earth Engine, GBIF, geocoding, and Vercel backend behavior depends on network access, upstream availability, credentials, and deployment environment variables. A successful frontend build does not validate those services.

## Submission-day release gate

Before submitting, have a teammate who did not build the app complete this checklist on the deployed Vercel URL:

- [ ] `/api/health` returns a healthy backend response and Earth Engine readiness is true.
- [ ] A point analysis succeeds for one land variable, NASA POWER temperature, NASA POWER precipitation, and an offshore sea-level coordinate; an inland sea-level query clearly reports no ocean data.
- [ ] A low-coverage variable (for example, GRACE after 2016) shows its real coverage and does not fabricate later observations.
- [ ] Verify boundary polygons, the displayed region type/source, the fast sample count, and the polygon valid-pixel count for the tested location.
- [ ] Verify the left search, layer gallery, and discoveries drawer do not overlap at the target presentation viewport.
- [ ] The sea-level contrast demo returns two charts, source/product, period, units, observation counts, slopes, and p-values; the direction statement matches the actual returned data.
- [ ] Story imagery year, numerical-analysis year, and source are visibly distinguished.
- [ ] Impact mode either returns its documented exposure metrics or shows an actionable service error; it is not described as causal impact.
- [ ] Test the deployed site in a fresh browser session with no local environment variables or cached API responses.
- [ ] Confirm the current year's official challenge rules, event work-start policy, submission format, English-language requirements, accessible links, and AI-use disclosure with the local event organizer.
- [ ] Submit a concise English project description, a short demo video or deck in the required format, source/data acknowledgments, and a working public project link.

## Judging narrative

Lead with **validity**: every statistic is attached to a named product, unit, period, and source. Then show **creativity** through the two-globe time comparison and interactive variable exploration. Explain **impact** as public science literacy and reproducible investigation, not as an unsupported prediction. Keep the presentation focused on one complete question—what changed, where, by how much, and how strong is the evidence—rather than listing every feature.

This brief describes the implementation and the checks still required; it does not claim that a Global Winner result can be guaranteed.
