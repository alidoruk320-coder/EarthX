export default function AnalysisPanel({ data }) {

    if (!data) {

        return (

            <div className="analysisPanel">

                <h2>🌍 Earth Analysis</h2>

                <p>

                    Search for a country or city to begin analysis.

                </p>

            </div>

        );

    }

    return (

        <div className="analysisPanel">

            <h2>

                {data.name}

            </h2>

            <div className="analysisGrid">

                <div className="infoCard">

                    <span>📍 Latitude</span>

                    <strong>{Number(data.lat).toFixed(4)}°</strong>

                </div>

                <div className="infoCard">

                    <span>📍 Longitude</span>

                    <strong>{Number(data.lon).toFixed(4)}°</strong>

                </div>

                <div className="infoCard">

                    <span>🌡 Temperature</span>

                    <strong>{data.temperature ?? "--"} °C</strong>

                </div>

                <div className="infoCard">

                    <span>💧 Humidity</span>

                    <strong>{data.humidity ?? "--"}%</strong>

                </div>

                <div className="infoCard">

                    <span>💨 Wind</span>

                    <strong>{data.wind ?? "--"} km/h</strong>

                </div>

                <div className="infoCard">

                    <span>🌧 Rain</span>

                    <strong>{data.rain ?? "--"} mm</strong>

                </div>

                <div className="infoCard">

                    <span>📅 Year</span>

                    <strong>{data.year}</strong>

                </div>

            </div>

            <div className="aiCard">

                <h3>
                    {data.mode === "live"
                        ? "🌦 Live Weather"
                        : data.mode === "climate"
                        ? "🌍 Climate Analysis"
                        : "🤖 AI Report"}
                </h3>

                <p>{data.summary}</p>

            </div>

        </div>

    );

}