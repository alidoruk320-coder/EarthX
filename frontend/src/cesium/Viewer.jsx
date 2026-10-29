import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";
import * as Cesium from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import {
  GIBS_LAYER_FOR_VARIABLE,
  GIBS_LAYERS,
  getGibsDate,
  getGibsTileUrl,
} from "../nasa/earthdata";

const EarthViewer = forwardRef((props, ref) => {
  const viewerRef = useRef(null);
  const containerRef = useRef(null);
  const baseLayerRef = useRef(null);
  const overlayLayerRef = useRef(null);
  const changeLayerRef = useRef(null);
  const searchBoundaryRef = useRef(null);
  const imageryRequestRef = useRef(0);
  const pointClickRef = useRef(props.onPointClick);
  const layerStatusRef = useRef(props.onLayerStatus);

  useEffect(() => {
    pointClickRef.current = props.onPointClick;
  }, [props.onPointClick]);

  useEffect(() => {
    layerStatusRef.current = props.onLayerStatus;
  }, [props.onLayerStatus]);

  function createProvider(layerKey, year) {
    const layer = typeof layerKey === "string" ? GIBS_LAYERS[layerKey] : layerKey;
    if (!layer) throw new Error(`Unknown NASA GIBS layer: ${layerKey}`);
    const level = Number(layer.tileMatrixSet.match(/Level(\d+)$/)?.[1]);
    return new Cesium.UrlTemplateImageryProvider({
      url: getGibsTileUrl(layerKey, year),
      tilingScheme: new Cesium.WebMercatorTilingScheme(),
      maximumLevel: level,
    });
  }

  function setGibsLayer(layerKey, year) {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;
    const layer = typeof layerKey === "string" ? GIBS_LAYERS[layerKey] : layerKey;
    if (!layer) throw new Error(`Unknown NASA GIBS layer: ${layerKey}`);

    const requestId = ++imageryRequestRef.current;
    const numericYear = Number(year);
    if (layer.temporal !== false && year != null
      && (!Number.isInteger(numericYear) || numericYear < layer.minYear || numericYear > layer.maxYear)) {
      const layerRef = layer.id === GIBS_LAYERS.trueColor.id ? baseLayerRef : overlayLayerRef;
      if (layerRef.current) {
        viewer.imageryLayers.remove(layerRef.current, true);
        layerRef.current = null;
      }
      layerStatusRef.current?.({
        status: "no-data",
        source: "NASA GIBS",
        layer: layer.title,
        variable: layer.title,
        year,
        requestedYear: year,
        detail: `${layer.minYear}–${layer.maxYear}`,
      });
      return;
    }
    const date = getGibsDate(layer, year);
    layerStatusRef.current?.({
      status: "loading",
      source: "NASA GIBS",
      layer: layer.title,
      variable: layer.title,
      year,
      requestedYear: year,
      date: date || undefined,
    });

    try {
      if (layer.id === GIBS_LAYERS.trueColor.id) {
        const provider = createProvider(layerKey, year);
        const nextLayer = viewer.imageryLayers.addImageryProvider(provider, 0);
        nextLayer.alpha = 1;
        if (overlayLayerRef.current) {
          viewer.imageryLayers.remove(overlayLayerRef.current, true);
          overlayLayerRef.current = null;
        }
        if (baseLayerRef.current) {
          viewer.imageryLayers.remove(baseLayerRef.current, true);
        }
        baseLayerRef.current = nextLayer;
      } else {
        const provider = createProvider(layerKey, year);
        const nextLayer = viewer.imageryLayers.addImageryProvider(provider);
        nextLayer.alpha = layer.alpha;
        if (overlayLayerRef.current) {
          viewer.imageryLayers.remove(overlayLayerRef.current, true);
        }
        overlayLayerRef.current = nextLayer;
      }
      if (changeLayerRef.current) viewer.imageryLayers.raiseToTop(changeLayerRef.current);

      const currentLayer = layer.id === GIBS_LAYERS.trueColor.id
        ? baseLayerRef.current
        : overlayLayerRef.current;
      currentLayer?.imageryProvider.errorEvent.addEventListener((error) => {
        if (requestId !== imageryRequestRef.current) return;
        layerStatusRef.current?.({
          status: "partial",
          source: "NASA GIBS",
          layer: layer.title,
          variable: layer.title,
          year,
          requestedYear: year,
          date: date || undefined,
          detail: error?.message,
        });
      });
      layerStatusRef.current?.({
        status: "live",
        source: "NASA GIBS",
        layer: layer.title,
        variable: layer.title,
        layerKey: layer.id,
        year,
        requestedYear: year,
        date: date || undefined,
      });
    } catch (error) {
      layerStatusRef.current?.({
        status: "error",
        source: "NASA GIBS",
        layer: layer.title,
        variable: layer.title,
        year,
        requestedYear: year,
        date: date || undefined,
        detail: error.message,
      });
      throw error;
    }
  }

  useImperativeHandle(ref, () => ({
    getViewer() {
      return viewerRef.current;
    },

    flyTo(lat, lon) {
      viewerRef.current?.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(lon, lat, 2500000),
        duration: 1.8,
      });
    },

    async setSearchBoundary(geojson) {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return false;
      if (searchBoundaryRef.current) {
        viewer.dataSources.remove(searchBoundaryRef.current, true);
        searchBoundaryRef.current = null;
      }
      if (!geojson || !["Polygon", "MultiPolygon"].includes(geojson.type)) return false;
      try {
        const source = await Cesium.GeoJsonDataSource.load(
          { type: "Feature", properties: {}, geometry: geojson },
          { clampToGround: true }
        );
        if (viewer.isDestroyed()) return false;
        for (const entity of source.entities.values) {
          if (entity.polygon) {
            entity.polygon.material = Cesium.Color.CYAN.withAlpha(0.12);
            entity.polygon.outline = true;
            entity.polygon.outlineColor = Cesium.Color.CYAN;
            entity.polygon.outlineWidth = 3;
          }
          if (entity.polyline) {
            entity.polyline.material = Cesium.Color.CYAN;
            entity.polyline.width = 3;
            entity.polyline.clampToGround = true;
          }
        }
        viewer.dataSources.add(source);
        searchBoundaryRef.current = source;
        await viewer.flyTo(source, { duration: 1.4, maximumHeight: 12000000 });
        return true;
      } catch (error) {
        console.warn("Could not display the searched place boundary:", error);
        return false;
      }
    },

    setGibsLayer,

    setChangeLayer(tileUrl) {
      const viewer = viewerRef.current;
      if (!viewer || viewer.isDestroyed()) return;
      if (changeLayerRef.current) {
        viewer.imageryLayers.remove(changeLayerRef.current, true);
        changeLayerRef.current = null;
      }
      if (!tileUrl) return;
      changeLayerRef.current = viewer.imageryLayers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: tileUrl,
          tilingScheme: new Cesium.WebMercatorTilingScheme(),
        })
      );
      changeLayerRef.current.alpha = 0.82;
    },

    setTrendLayer(variable, year) {
      setGibsLayer(GIBS_LAYER_FOR_VARIABLE[variable] || "trueColor", year);
    },

    clearStoryLayer() {
      imageryRequestRef.current += 1;
      const viewer = viewerRef.current;
      if (overlayLayerRef.current) {
        viewer?.imageryLayers.remove(overlayLayerRef.current, true);
        overlayLayerRef.current = null;
      }
    },
  }), []);

  useEffect(() => {
    const viewer = new Cesium.Viewer(containerRef.current, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      baseLayer: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      navigationHelpButton: false,
      sceneModePicker: false,
      selectionIndicator: false,
      infoBox: false,
    });
    viewerRef.current = viewer;
    const cameraController = viewer.scene.screenSpaceCameraController;
    cameraController.enableTilt = true;
    cameraController.tiltEventTypes = [
      Cesium.CameraEventType.RIGHT_DRAG,
      Cesium.CameraEventType.PINCH,
    ];
    cameraController.zoomEventTypes = [
      Cesium.CameraEventType.WHEEL,
      Cesium.CameraEventType.PINCH,
    ];
    viewer.scene.globe.enableLighting = true;
    viewer.scene.skyAtmosphere.show = true;
    viewer.scene.globe.depthTestAgainstTerrain = true;

    const initialLocation = props.initialLocation;
    if (initialLocation) {
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          initialLocation.lon,
          initialLocation.lat,
          3500000
        ),
        duration: 0,
      });
    } else {
      viewer.camera.flyHome(0);
    }

    const initialLayer = props.initialLayer || "trueColor";
    if (initialLayer !== "trueColor") setGibsLayer("trueColor", null);
    setGibsLayer(
      initialLayer,
      props.initialYear ?? (initialLayer === "trueColor" ? null : new Date().getUTCFullYear())
    );

    viewer.screenSpaceEventHandler.setInputAction((click) => {
      const cartesian = viewer.camera.pickEllipsoid(
        click.position,
        viewer.scene.globe.ellipsoid
      );
      if (!cartesian || !pointClickRef.current) return;
      const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
      pointClickRef.current(
        Cesium.Math.toDegrees(cartographic.latitude),
        Cesium.Math.toDegrees(cartographic.longitude)
      );
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      imageryRequestRef.current += 1;
      if (!viewer.isDestroyed()) viewer.destroy();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      id={props.containerId || "cesiumContainer"}
      className="cesiumContainer"
    />
  );
});

export default EarthViewer;
