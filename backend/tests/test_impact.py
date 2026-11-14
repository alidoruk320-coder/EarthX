import unittest
from unittest.mock import MagicMock, patch

from app.routers import impact


class ImpactAnalysisTests(unittest.TestCase):
    def test_population_mosaic_gets_source_projection_before_reduce_resolution(self):
        fake_ee = MagicMock()
        region = MagicMock(name="region")
        fake_ee.Geometry.Rectangle.return_value = region

        population_collection = MagicMock(name="population_collection")
        population_collection.filterDate.return_value = population_collection
        population_collection.select.return_value = population_collection
        population_image = MagicMock(name="population_mosaic")
        population_collection.mosaic.return_value = population_image
        source_projection = MagicMock(name="source_projection")
        population_collection.first.return_value.select.return_value.projection.return_value = source_projection
        projected_population = MagicMock(name="projected_population")
        population_image.setDefaultProjection.return_value = projected_population
        population_at_1km = MagicMock(name="population_at_1km")
        projected_population.reduceResolution.return_value = population_at_1km
        population_at_1km.reproject.return_value.reduceRegion.return_value.get.return_value = 1200

        daily_lights = MagicMock(name="daily_lights")
        annual_collection = MagicMock(name="annual_collection")
        daily_lights.filterDate.return_value = annual_collection
        annual_image = MagicMock(name="annual_image")
        annual_collection.map.return_value.mean.return_value.rename.return_value = annual_image
        fake_ee.ImageCollection.side_effect = [population_collection, daily_lights]
        fake_ee.Dictionary.return_value.combine.return_value.getInfo.return_value = {
            "population_total": 1200,
            "baseline": 1.0,
            "recent": 1.5,
            "radiance_change": 0.5,
        }
        with patch.object(impact, "ee", fake_ee), patch.object(
            impact, "is_gee_initialized", return_value=True
        ):
            impact.regional_exposure(south=10, north=11, west=20, east=21)

        population_image.setDefaultProjection.assert_called_once_with(source_projection)
        projected_population.reduceResolution.assert_called_once()


if __name__ == "__main__":
    unittest.main()
