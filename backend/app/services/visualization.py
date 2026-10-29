import ee
from app.config import VARIABLES


def _apply_quality_masks(collection, cfg):
    quality_band = cfg.get("quality_band")
    if not quality_band:
        return collection

    def mask_low_quality(image):
        quality = image.select(quality_band)
        # MOD11A2 QC_Day bits 0-1: 0 means good-quality LST.
        mask = quality.bitwiseAnd(3).eq(0)
        return image.updateMask(mask)

    return collection.map(mask_low_quality)


def get_tile_url(variable: str, year: int) -> str:
    """
    Verilen değişken + yıl için Cesium'a doğrudan verilebilecek
    {z}/{x}/{y} formatlı renkli imagery tile URL'sini döner.
    """
    if variable not in VARIABLES:
        raise ValueError(f"Bilinmeyen değişken: {variable}")

    cfg = VARIABLES[variable]
    source = cfg.get("source", "NASA")

    collection = _apply_quality_masks(
        ee.ImageCollection(cfg["collection"])
        .filterDate(f"{year}-01-01", f"{year + 1}-01-01"), cfg
    )

    try:
        image_count = collection.size().getInfo()
        if image_count == 0:
            raise ValueError(
                f"Bu değişken/tarih için {source} verisi mevcut değil: {variable}, {year}."
            )

        yearly = collection.select(cfg["band"])
        image = yearly.sum() if cfg.get("aggregation") == "sum" else yearly.mean()
        scaled = image.multiply(cfg["scale_factor"]).add(cfg["offset"])

        vis_image = scaled.visualize(
            min=cfg["vis_min"],
            max=cfg["vis_max"],
            palette=cfg["palette"],
        )

        map_id_dict = vis_image.getMapId()
        return map_id_dict["tile_fetcher"].url_format
    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"Bu değişken/tarih için {source} verisi şu anda alınamıyor: {error}"
        ) from error


def get_change_tile_url(variable: str, start_year: int, end_year: int) -> str:
    if variable not in VARIABLES:
        raise ValueError(f"Bilinmeyen değişken: {variable}")
    cfg = VARIABLES[variable]
    first_year = cfg.get("start_year", 2000)
    last_year = cfg.get("latest_complete_year", 2100)
    if start_year < first_year or end_year > last_year or end_year - start_year < 2:
        raise ValueError("Değişim haritası için en az üç yıllık geçerli bir dönem seçin.")

    collection = _apply_quality_masks(ee.ImageCollection(cfg["collection"]), cfg)

    try:
        image_count = (
            collection
            .filterDate(f"{start_year}-01-01", f"{end_year + 1}-01-01")
            .size()
            .getInfo()
        )
        if image_count == 0:
            raise ValueError(
                f"Bu değişken/tarih aralığı için NASA verisi mevcut değil: "
                f"{variable}, {start_year}-{end_year}."
            )

        empty_image = ee.Image.constant(0).rename(cfg["band"]).updateMask(
            ee.Image.constant(0)
        )

        def annual_image(year):
            year = ee.Number(year)
            start = ee.Date.fromYMD(year, 1, 1)
            annual = (
                collection
                .filterDate(start, start.advance(1, "year"))
                .select(cfg["band"])
                .merge(ee.ImageCollection.fromImages([empty_image]))
            )
            reducer = ee.Reducer.sum() if cfg.get("aggregation") == "sum" else ee.Reducer.mean()
            annual = annual.reduce(reducer).rename(cfg["band"])
            annual = annual.multiply(cfg["scale_factor"])
            # For LST, Kelvin-to-Celsius conversion commutes with the mean
            # and regression. For other variables this remains the catalog scale.
            annual = annual.add(cfg["offset"]).rename("value")
            year_band = ee.Image.constant(year).toFloat().rename("year").updateMask(
                annual.mask()
            )
            return year_band.addBands(annual)

        annual_collection = ee.ImageCollection.fromImages(
            ee.List.sequence(start_year, end_year).map(annual_image)
        )
        slope = (
            annual_collection
            .select(["year", "value"])
            .reduce(ee.Reducer.linearFit())
            .select("scale")
        )

        world = ee.Geometry.Rectangle([-180, -80, 180, 80], "EPSG:4326", False)
        percentile_scale = max(int(cfg["scale_meters"]), 50000)
        percentile_result = slope.abs().reduceRegion(
            reducer=ee.Reducer.percentile([95]),
            geometry=world,
            scale=percentile_scale,
            maxPixels=100_000_000,
            bestEffort=True,
            tileScale=4,
        ).getInfo()
        percentile = next(iter(percentile_result.values()), None)
        if percentile is None:
            raise ValueError(
                f"Bu değişken/tarih aralığı için hesaplanabilir trend verisi yok: "
                f"{variable}, {start_year}-{end_year}."
            )

        color_limit = max(float(percentile), 1e-9)
        hotspots = slope.updateMask(slope.abs().gte(color_limit)).visualize(
            min=-color_limit,
            max=color_limit,
            palette=["a50026", "d73027", "f46d43", "ffffbf", "abd9e9", "4575b4", "313695"],
        )
        return hotspots.getMapId()["tile_fetcher"].url_format
    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"NASA küresel değişim karosu üretilemedi: {error}"
        ) from error
