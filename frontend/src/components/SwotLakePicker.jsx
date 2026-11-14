import { useState } from "react";

const LAKE_CHOICES = [
  {
    id: "large_aral",
    label: { en: "Large Aral Sea", tr: "Büyük Aral Gölü" },
    detail: {
      en: "Verified SWOT LakeSP feature · irregular water-surface observations",
      tr: "Doğrulanmış SWOT LakeSP göl özelliği · düzensiz su yüzeyi gözlemleri",
    },
    lat: 45.149449,
    lon: 58.560971,
  },
  {
    id: "lake_chad",
    label: { en: "Lake Chad", tr: "Çad Gölü" },
    detail: {
      en: "Verified SWOT LakeSP feature · irregular water-surface observations",
      tr: "Doğrulanmış SWOT LakeSP göl özelliği · düzensiz su yüzeyi gözlemleri",
    },
    lat: 13.251389,
    lon: 15.173245,
  },
];

const INFO_CHOICES = [
  {
    id: "how-it-works",
    label: { en: "How SWOT works", tr: "SWOT verisi nasıl çalışır?" },
    detail: {
      en: "Choose a verified lake to load cached NASA PO.DAAC Hydrocron observations.",
      tr: "Önbellekteki NASA PO.DAAC Hydrocron gözlemlerini yüklemek için doğrulanmış bir göl seçin.",
    },
    body: {
      en: "The plotted dots are individual SWOT LakeSP water-surface-elevation observations for the lake feature. The dashed line is an exploratory Sen slope over their irregular dates, not a significance test. These are not measurements at the searched location, annual averages, or direct measurements of lake volume.",
      tr: "Grafikteki noktalar, göl özelliğine ait tekil SWOT LakeSP su yüzeyi yüksekliği gözlemleridir. Kesikli çizgi düzensiz tarihler üzerindeki keşifsel Sen eğimidir; anlamlılık testi değildir. Bunlar aranan konumun doğrudan ölçümü, yıllık ortalama veya göl hacminin doğrudan ölçümü değildir.",
    },
  },
  {
    id: "coverage",
    label: { en: "Coverage and limitations", tr: "Kapsam ve sınırlar" },
    detail: {
      en: "Only two verified cached lakes are currently available.",
      tr: "Şu anda yalnızca önbellekte doğrulanmış iki göl destekleniyor.",
    },
    body: {
      en: "The current cache covers only the Large Aral Sea and Lake Chad. Other locations are not supported. EarthVerse shows an exploratory Sen slope over the irregular observation dates, but does not calculate annual averages, a Mann–Kendall test, or a p-value. Quality and ice flags are retained as provided; no undocumented filter is applied.",
      tr: "Mevcut önbellek yalnızca Büyük Aral Gölü ve Çad Gölü'nü kapsar; diğer konumlar desteklenmez. EarthVerse düzensiz gözlem tarihleri üzerinden keşifsel Sen eğimi gösterir; ancak yıllık ortalama, Mann–Kendall testi veya p-değeri hesaplamaz. Kalite ve buz bayrakları kaynaktan geldiği gibi korunur; belgelenmemiş filtre uygulanmaz.",
    },
  },
];

export default function SwotLakePicker({ language = "en", onSelectLake }) {
  const isTurkish = language === "tr";
  const [selectedInfo, setSelectedInfo] = useState(null);
  const info = INFO_CHOICES.find((choice) => choice.id === selectedInfo);

  return (
    <section className="analysisPanel swotLakePicker" aria-labelledby="swotLakePickerTitle">
      <div className="panelEyebrow">NASA SWOT · LAKES</div>
      <h2 id="swotLakePickerTitle">
        {isTurkish ? "SWOT göl gözlemleri" : "SWOT lake observations"}
      </h2>
      <p className="swotPickerIntro">
        {isTurkish
          ? "Bu veri şu anda yalnızca iki doğrulanmış göl için kullanılabilir. Analiz için bir göl seçin; Türkiye gibi diğer konumlar henüz desteklenmiyor."
          : "This dataset is currently available for only two verified lakes. Choose a lake to analyze; other locations are not supported yet."}
      </p>
      <div className="swotChoiceGrid">
        {LAKE_CHOICES.map((choice) => (
          <button
            className="swotChoiceCard"
            key={choice.id}
            onClick={() => onSelectLake(choice)}
          >
            <strong>{choice.label[language] || choice.label.en}</strong>
            <span>{choice.detail[language] || choice.detail.en}</span>
            <b>{isTurkish ? "GÖLÜ ANALİZ ET →" : "ANALYZE LAKE →"}</b>
          </button>
        ))}
        {INFO_CHOICES.map((choice) => (
          <button
            className={`swotChoiceCard info ${selectedInfo === choice.id ? "active" : ""}`}
            key={choice.id}
            aria-pressed={selectedInfo === choice.id}
            onClick={() => setSelectedInfo((current) => current === choice.id ? null : choice.id)}
          >
            <strong>{choice.label[language] || choice.label.en}</strong>
            <span>{choice.detail[language] || choice.detail.en}</span>
            <b>{isTurkish ? "BİLGİYİ GÖSTER ↓" : "SHOW DETAILS ↓"}</b>
          </button>
        ))}
      </div>
      {info && (
        <div className="swotInfoDetail" role="status">
          <strong>{info.label[language] || info.label.en}</strong>
          <p>{info.body[language] || info.body.en}</p>
        </div>
      )}
    </section>
  );
}
