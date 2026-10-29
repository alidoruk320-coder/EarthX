export default function YearSlider({
  year,
  setYear,
  language = "en",
  minYear = 2002,
  maxYear = 2026,
  disabled = false,
  notice = "",
}) {
  const isTurkish = language === "tr";
  const yearSpan = maxYear - minYear;
  const labels = [0, 1 / 3, 2 / 3, 1].map((fraction) =>
    Math.round(minYear + yearSpan * fraction)
  );
  return (
    <div className="yearSlider">

      <div className="yearSliderHeader">

        <div>
          <div className="yearCaption">
            {isTurkish ? "ZAMAN AYNASI" : "TIME MIRROR"}
          </div>

          <div className="yearValue">
            {year}
          </div>
        </div>

        <div className="yearLatest">
          {disabled ? (isTurkish ? "ZAMANSIZ" : "STATIC") : (isTurkish ? "GÜNCEL" : "LATEST")}
          <strong>{disabled ? "—" : maxYear}</strong>
        </div>

      </div>

      <input
        type="range"
        min={minYear}
        max={maxYear}
        step="1"
        value={year}
        disabled={disabled}
        onChange={(e) =>
          setYear(Number(e.target.value))
        }
      />

      {notice && <small className="yearRangeNotice" role="status">{notice}</small>}

      <div className="yearLabels">
        {labels.map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
      </div>

    </div>
  );
}