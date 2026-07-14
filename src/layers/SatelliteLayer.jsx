import * as Cesium from "cesium";

let satelliteLayer = null;

export function addSatelliteLayer(viewer, url) {

    if (satelliteLayer) {

        viewer.imageryLayers.remove(satelliteLayer);

    }

    satelliteLayer = viewer.imageryLayers.addImageryProvider(

        new Cesium.UrlTemplateImageryProvider({

            url: url,

            maximumLevel: 9

        })

    );

}

export function removeSatelliteLayer(viewer) {

    if (satelliteLayer) {

        viewer.imageryLayers.remove(satelliteLayer);

        satelliteLayer = null;

    }

}