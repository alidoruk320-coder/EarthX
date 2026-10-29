import * as Cesium from "cesium";

let boundarySource = null;

export async function loadBoundary(viewer, geojson) {

    if (boundarySource) {

        viewer.dataSources.remove(boundarySource);

    }

    boundarySource = await Cesium.GeoJsonDataSource.load(

        geojson,

        {

            stroke: Cesium.Color.RED,

            fill: Cesium.Color.RED.withAlpha(0.12),

            strokeWidth: 3,

            clampToGround: true

        }

    );

    viewer.dataSources.add(boundarySource);

    await viewer.flyTo(boundarySource, {

        duration: 2

    });

}