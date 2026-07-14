import {
    useEffect,
    useRef,
    forwardRef,
    useImperativeHandle
} from "react";

import * as Cesium from "cesium";

import "cesium/Build/Cesium/Widgets/widgets.css";

import { loadBoundary } from "../layers/BoundaryLayer";

const EarthViewer = forwardRef((props, ref) => {

    const viewerRef = useRef(null);

    const containerRef = useRef(null);

    useImperativeHandle(ref, () => ({

        getViewer() {

            return viewerRef.current;

        },

        flyTo(lat, lon) {

            viewerRef.current.camera.flyTo({

                destination:

                    Cesium.Cartesian3.fromDegrees(

                        Number(lon),

                        Number(lat),

                        2500000

                    ),

                duration:2

            });

        },

        async showBoundary(geojson){

            await loadBoundary(

                viewerRef.current,

                geojson

            );

        }

    }));

    useEffect(()=>{

        Cesium.Ion.defaultAccessToken =
            import.meta.env.VITE_CESIUM_TOKEN;

        const viewer=new Cesium.Viewer(

            containerRef.current,

            {

                animation:false,

                timeline:false,

                baseLayerPicker:false,

                fullscreenButton:false,

                geocoder:false,

                homeButton:false,

                navigationHelpButton:false,

                sceneModePicker:false,

                selectionIndicator:false,

                infoBox:false

            }

        );

        viewer.scene.globe.enableLighting=true;

        viewer.scene.skyAtmosphere.show=true;

        viewer.scene.globe.depthTestAgainstTerrain=true;

        viewer.camera.flyHome(0);

        viewerRef.current=viewer;

        return()=>{

            if(!viewer.isDestroyed()){

                viewer.destroy();

            }

        };

    },[]);

    return(

        <div

            ref={containerRef}

            id="cesiumContainer"

            style={{

                width:"100%",

                height:"100vh"

            }}

        />

    );

});

export default EarthViewer;