import { useState } from "react";

// src/pages/Landing.jsx
function Landing({ onEnter, language, setLanguage }) {
  const assetBase = import.meta.env.BASE_URL;
  const isTurkish = language === "tr";
  const [tourStep, setTourStep] = useState(0);
  const [tourComplete, setTourComplete] = useState(() => localStorage.getItem("twinearth-guide-v2") === "complete");

  const tourSteps = isTurkish ? [
    {
      title: "Dünya verilerini nasıl okuyacaksınız?",
      body: "TwinEarth farklı uydu veri katmanlarını, yılları ve istatistikleri aynı Dünya üzerinde bir araya getirir. Bu kısa tur, gördüğünüz renklerin ve sayıların ne söylediğini açıklar.",
      points: ["Her katmanın kaynağı ve yılı üstte gösterilir.", "Veri yoksa bu, sıfır değişim demek değildir."],
    },
    {
      title: "Soldaki görsel katmanlar",
      body: "Sol panelde Dünya üzerinde gösterilecek harita katmanını seçin. Bu görseller değişkenin istatistiksel analizinden ayrıdır.",
      image: `${assetBase}images/tour-visual.webp`,
      imageAlt: "Soldaki görsel katman panelini gösteren Dünya ekranı",
      points: ["Gerçek Renk uydu görüntüsünü; Bitki Örtüsü, Sıcaklık, Kar, Deniz Yüzeyi Sıcaklığı ve Yağış tematik katmanlarını gösterir.", "Renklerin anlamı seçili katmana göre değişir; her katmanın ölçüsü ve birimi farklıdır.", "Tüm Worldview katmanlarını ara düğmesiyle ek görsel katmanları bulabilirsiniz."],
    },
    {
      title: "Sağ panelde analiz değişkenini seçin",
      body: "Sağ üstteki açılır menü, istatistiksel analizde incelenecek değişkeni belirler. Bu seçim soldaki görsel katmandan bağımsızdır.",
      image: `${assetBase}images/tour-analysis.webp`,
      imageAlt: "Sağdaki istatistiksel analiz değişken menüsünü gösteren Dünya ekranı",
      points: ["Bir yer arayın veya kürede bir noktaya tıklayın; seçili değişkenin zaman serisi ve istatistikleri yüklenir.", "Menüde sıcaklık, yağış, bitki örtüsü, toprak nemi ve diğer veri ürünleri bulunur; her ürünün kapsadığı dönem farklı olabilir.", "Alttaki zaman kaydırıcısı harita yılını değiştirir. Kaynakta veri yoksa bu, sıfır değişim anlamına gelmez."],
    },
    {
      title: "p-değeri ve Sen eğimi",
      body: "Yıllık zaman serisini, Sen eğimi çizgisini ve bu eğilime ait istatistiksel kanıtı birlikte okuyun.",
      points: ["p-değeri, trend yok varsayımı altında bu kadar uç bir sonucun görülmesine ilişkin kanıttır. p<0,05 istatistiksel kanıt sayılır; trendin doğru olma olasılığının %95 olduğu anlamına gelmez.", "Sen eğimi yıllık ortanca değişim hızını verir; grafikteki kesikli çizgi bu eğimi gösterir. Eksik yıllar çizgide birleştirilmez.", "Korelasyon nedensellik kanıtı değildir; sonuçları veri dönemi, kaynak ve doğal değişkenlikle birlikte yorumlayın."],
    },
    {
      title: "Anlık Keşifler ve harita modları",
      body: "Sol alttaki hazır örneklerle belirli konum ve veri kümelerini hemen açabilir, soldaki panelden farklı modlara geçebilirsiniz.",
      image: `${assetBase}images/tour-discoveries.webp`,
      imageAlt: "Dünya ekranında örnek konumları gösteren Anlık Keşifler paneli",
      points: ["Anlık Keşifler; SWOT göl gözlemleri, Sahel bitki örtüsü ve GRACE su depolama bağlamı gibi örnekleri açar.", "Cascade yıllık değişkenleri gecikmeli karşılaştırır; korelasyon neden-sonuç kanıtlamaz. Impact, nüfus ve gece ışığı maruziyet bağlamı sunar.", "Nokta Modu ile küreye tıklayın; Küresel Hikâye farklı yerleri ve yılları karşılaştırır. GBIF kayıtları hayvan sayısı değildir."],
    },
    {
      title: "PDF ne zaman kullanılabilir?",
      body: "Rapor düğmeleri yalnızca doğrulanmış uydu veri serisi rapor için yeterliyse etkinleşir.",
      points: ["Kaynak, ürün kimliği, koordinat, birim ve yıllık gözlem sayısı rapora eklenir.", "En az 8 geçerli yıllık gözlem olmalı ve seri seçili bitiş yılını kapsamalıdır.", "NASA kaynağı kullanmak istatistiksel sonucun kusursuz veya %100 kesin olduğu anlamına gelmez; belirsizlik raporda belirtilir."],
    },
  ] : [
    {
      title: "How to read Earth data",
      body: "TwinEarth combines satellite data layers, years, and statistics on one globe. This short guide explains what the colors and numbers mean.",
      points: ["The selected layer and year appear above the globe.", "Missing data does not mean zero change."],
    },
    {
      title: "Visual layers on the left",
      body: "Choose the map layer shown on the globe from the left panel. These visual layers are separate from the statistical analysis of a variable.",
      image: `${assetBase}images/tour-visual.webp`,
      imageAlt: "Earth screen highlighting the visual layer gallery on the left",
      points: ["True Color shows satellite imagery; Vegetation, Temperature, Snow, Sea Surface Temperature, and Precipitation show thematic layers.", "Color meanings depend on the selected layer; each uses its own measurement scale and units.", "Use Search Full Worldview Catalog to find additional visual layers."],
    },
    {
      title: "Choose an analysis variable on the right",
      body: "The dropdown at the top right selects which variable to analyze statistically. It is independent of the visual map layer on the left.",
      image: `${assetBase}images/tour-analysis.webp`,
      imageAlt: "Earth screen highlighting the statistical analysis variable menu on the right",
      points: ["Search for a place or click the globe to load the selected variable's time series and statistics.", "The menu includes temperature, precipitation, vegetation, soil moisture, and other products; each dataset has its own coverage period.", "The bottom timeline changes the map year. Missing source data does not mean zero change."],
    },
    {
      title: "p-value and Sen's slope",
      body: "Read the annual time series, Sen slope line, and statistical evidence together.",
      points: ["The p-value measures evidence against a no-trend assumption. p<0.05 is statistical evidence; it is not a 95% probability that the trend is true.", "Sen's slope estimates the median annual rate of change; the dashed chart line shows that slope. Missing years are not connected in the observed series.", "Correlation is not proof of causation; interpret results with the period, source, and natural variability in mind."],
    },
    {
      title: "Instant Discoveries and map modes",
      body: "Use the curated examples at the lower left to jump into prepared locations and datasets, or choose a mode from the left panel.",
      image: `${assetBase}images/tour-discoveries.webp`,
      imageAlt: "Instant Discoveries panel showing example locations on the Earth screen",
      points: ["Instant Discoveries opens examples such as SWOT lake observations, Sahel vegetation, and GRACE water-storage context.", "Cascade compares annual variables with time lags; correlation does not prove cause. Impact summarizes population and night-light exposure context.", "Draw Mode lets you click a location; Global Story compares places and years. GBIF records are observations, not animal counts."],
    },
    {
      title: "When can you export a PDF?",
      body: "Report buttons activate only when a verified satellite-data series is sufficient for a report.",
      points: ["Reports include the source, product ID, coordinates, unit, and annual observation count.", "At least 8 valid annual observations are required, and the series must cover the selected end year.", "Using NASA data does not make a statistical conclusion perfect or 100% certain; uncertainty is stated in the report."],
    },
  ];

  function finishTour() {
    localStorage.setItem("twinearth-guide-v2", "complete");
    setTourComplete(true);
  }

  return (
    <div className="landing">
      <div className="stars"></div>

      <div className="topLogo">
        <img src={`${assetBase}images/logo.png`} alt="Logo" />
        <span>{isTurkish ? "NexusEarth 3B" : "NexusEarth 3D"}</span>
      </div>

      <div className="powered">
        {isTurkish ? "NASA Space Apps Yarışması 2026" : "NASA Space Apps Challenge 2026"}
      </div>

      <div className="languageBar" aria-label="Language selector">
        <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
        <button className={language === "tr" ? "active" : ""} onClick={() => setLanguage("tr")}>TR</button>
      </div>

      <div className="landingContent">
        <div className="badge">
          {isTurkish ? "NE DEĞİŞTİ? NEREDE? NE KADAR? ANLAMLI MI?" : "WHAT CHANGED? WHERE? HOW MUCH? IS IT SIGNIFICANT?"}
        </div>

        <h1>NEXUSEARTH 3D</h1>
        <p className="subtitle" style={{ fontWeight: 600, color: '#8fc8da', marginBottom: '12px' }}>
          {isTurkish ? "Yapay zekâ destekli Dünya sistemi trend dedektifi" : "AI-Assisted Earth System Trend Detective"}
        </p>

        <p className="subtitle">
          {isTurkish ? "NASA uydu gözlemleri ve NASA modellerinden üretilen verilerle çalışan etkileşimli bir Dünya sistemi. Değişimi uzay ve zaman içinde görselleştirip seçili noktalarda istatistiksel olarak inceliyoruz." : "An interactive Earth system using NASA satellite observations and NASA model products. We visualize change across space and time and statistically examine selected locations."}
        </p>

        <p className="sciencePrimer">
          {isTurkish
            ? "Bilimsel sonuçları okuma: p-değeri, trend yok varsayımına karşı kanıtı ölçer; p<0,05, trendin doğru olma olasılığının %95 olduğu anlamına gelmez. Sen eğimi yıllık ortanca değişimi verir. Renkler ölçülen değeri, anlamlılık ise istatistik testini gösterir."
            : "Reading the science: a p-value measures evidence against no trend; p<0.05 does not mean there is a 95% chance the trend is true. Sen's slope is the median change per year. Colors show measured values; significance comes from the statistical test."}
        </p>

        <button onClick={onEnter}>
          {isTurkish ? "DÜNYAYI TARA VE TRENDLERİ BUL ➔" : "SCAN EARTH & DETECT TRENDS ➔"}
        </button>

        <div className="features">
          <div className="featureCard">
            <div className="icon">01 / {isTurkish ? "BUL" : "DETECT"}</div>
            <h3>{isTurkish ? "Anlamlılık Motoru" : "Significance Engine"}</h3>
            <p>{isTurkish ? "Sen eğimi ve Mann-Kendall ile sağlam istatistiksel test." : "Sen's Slope & Mann-Kendall rigorous statistical testing."}</p>
          </div>

          <div className="featureCard">
            <div className="icon">02 / {isTurkish ? "KARŞILAŞTIR" : "COMPARE"}</div>
            <h3>{isTurkish ? "Bölgesel Trendleri İncele" : "Explore Regional Trends"}</h3>
            <p>{isTurkish ? "Farklı yerleri arayıp aynı değişken için trend sonuçlarını karşılaştırın." : "Search different places and compare trend results for the same variable."}</p>
          </div>

          <div className="featureCard">
            <div className="icon">03 / {isTurkish ? "İNCELE" : "INVESTIGATE"}</div>
            <h3>{isTurkish ? "Yapay Zekâ Araştırmacısı" : "AI Investigator"}</h3>
            <p>{isTurkish ? "Bilimsel sınırları koruyan bağlamsal yapay zekâ raporları." : "Contextual AI reports respecting scientific boundaries."}</p>
          </div>
        </div>
      </div>

      <div className="earthHero">
        <img src={`${assetBase}images/earth.png`} alt="Earth" />
      </div>

      {!tourComplete && (
        <div className="onboardingScrim" role="dialog" aria-modal="true" aria-labelledby="tourTitle">
          <div className="onboardingLanguage" aria-label="Language selector">
            <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
            <button className={language === "tr" ? "active" : ""} onClick={() => setLanguage("tr")}>TR</button>
          </div>
          <section className="onboardingCard">
            <div className="onboardingBrand">TWIN EARTH <span>FIELD GUIDE</span></div>
            <div className="onboardingProgress">
              <span>{String(tourStep + 1).padStart(2, "0")} / {String(tourSteps.length).padStart(2, "0")}</span>
              <div><span style={{ width: `${((tourStep + 1) / tourSteps.length) * 100}%` }} /></div>
            </div>
            <h2 id="tourTitle">{tourSteps[tourStep].title}</h2>
            <p className="onboardingBody">{tourSteps[tourStep].body}</p>
            {tourSteps[tourStep].image && <figure className="onboardingImage">
              <img src={tourSteps[tourStep].image} alt={tourSteps[tourStep].imageAlt} />
            </figure>}
            <ul className="onboardingPoints">
              {tourSteps[tourStep].points.map((point) => <li key={point}>{point}</li>)}
            </ul>
            <div className="onboardingActions">
              <button className="onboardingBack" disabled={tourStep === 0} onClick={() => setTourStep((step) => Math.max(0, step - 1))}>
                {isTurkish ? "GERİ" : "BACK"}
              </button>
              {tourStep < tourSteps.length - 1 ? (
                <button className="onboardingNext" onClick={() => setTourStep((step) => step + 1)}>
                  {isTurkish ? "İLERİ" : "NEXT"} →
                </button>
              ) : (
                <button className="onboardingNext" onClick={finishTour}>
                  {isTurkish ? "KEŞFE BAŞLA" : "START EXPLORING"} →
                </button>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default Landing;
