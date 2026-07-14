export function createInfoPanel(){

    const panel=document.createElement("div");

    panel.className="infoPanel";

    panel.innerHTML=`

        <h2>EarthVerse AI</h2>

        <hr>

        <p><b>Latitude</b></p>

        <span id="lat">-</span>

        <p><b>Longitude</b></p>

        <span id="lon">-</span>

        <p><b>Temperature</b></p>

        <span id="temp">-</span>

        <p><b>Vegetation</b></p>

        <span id="rain">-</span>

        <p><b>Risk Score</b></p>

       <span id="solar">-</span>

    `;

    return panel;

}