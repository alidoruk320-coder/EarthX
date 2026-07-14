export default function LayerSelector({

    layer,

    setLayer

}) {

    return (

        <div className="layerSelector">

            <select

                value={layer}

                onChange={(e) =>

                    setLayer(e.target.value)

                }

            >

                <option value="earth">

                    🌍 Earth

                </option>

                <option value="truecolor">

                    🛰 True Color

                </option>

                <option value="temperature">

                    🌡 Surface Temperature

                </option>

                <option value="ndvi">

                    🌱 Vegetation (NDVI)

                </option>

                <option value="fires">

                    🔥 Wildfires

                </option>

            </select>

        </div>

    );

}