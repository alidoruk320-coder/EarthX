export function createTimeline(){

    const div=document.createElement("div");

    div.className="timeline";

    div.innerHTML=`

        <span>2025</span>

        <input
            id="yearSlider"
            type="range"
            min="2025"
            max="2100"
            value="2025"
        >

        <span id="yearLabel">2025</span>

    `;

    return div;

}