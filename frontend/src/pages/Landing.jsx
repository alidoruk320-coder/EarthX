import { useState } from "react";

// src/pages/Landing.jsx
function Landing({ onEnter, language, setLanguage }) {
  const assetBase = import.meta.env.BASE_URL;
  const isTurkish = language === "tr";
  const [tourStep, setTourStep] = useState(0);
  const [tourComplete, setTourComplete] = useState(() => localStorage.getItem("twinearth-guide-v1") === "complete");

  const tourSteps = isTurkish ? [
    {
      title: "Dünya verilerini nasıl okuyacaksınız?",
      body: "TwinEarth farklı uydu veri katmanlarını, yılları ve istatistikleri aynı Dünya üzerinde bir araya getirir. Bu kısa tur, gördüğünüz renklerin ve sayıların ne söylediğini açıklar.",
      points: ["Her katmanın kaynağı ve yılı üstte gösterilir.", "Veri yoksa bu, sıfır değişim demek değildir."],
    },
    {
      title: "Mavi her zaman soğuk demek değildir",
      body: "Rengin anlamı seçili katmana bağlıdır.",
      points: ["Uydu tabanı hava fotoğrafıdır; görüntü tarihi bölgeye göre değişebilir ve her yerde ev ayrıntısı bulunmayabilir.", "Sıcaklık katmanı: mavi daha düşük, sarı-kırmızı daha yüksek yüzey sıcaklığı gösterir.", "NDVI, toprak nemi ve GRACE katmanlarının her birinin farklı ölçeği ve birimi vardır. Renk, artış/azalış veya iyi/kötü anlamına gelmez."],
    },
    {
      title: "Yıl seçimi ve veri kapsamı",
      body: "Alttaki zaman kaydırıcısı seçili uydu gözlem yılını değiştirir. Üstteki katman etiketi hangi değişkenin hangi yıl için yüklendiğini gösterir.",
      points: ["Benzer yıllardaki ölçümlerin renkleri birbirine yakın olabilir; harita yine de yeni yılın verisini yükler.", "GRACE V04 verisi 2017-01'de sona eriyor; yıllık analiz son tam yıl olan 2016'da biter. Daha sonraki seçili yıllarda mevcut kapsam açıkça belirtilir.", "Uydu tabanının çekim tarihi seçilen yıldan farklı olabilir; yıl kaydırıcısı tematik ölçüm katmanını ve analiz dönemini değiştirir."],
    },
    {
      title: "p-değeri ve Sen eğimi",
      body: "Yıllık zaman serisini, Sen eğimi çizgisini ve bu eğilime ait istatistiksel kanıtı birlikte okuyun.",
      points: ["p-değeri, trend yok varsayımı altında bu kadar uç bir sonucun görülmesine ilişkin kanıttır. p<0,05 istatistiksel kanıt sayılır; trendin doğru olma olasılığının %95 olduğu anlamına gelmez.", "Sen eğimi yıllık ortanca değişim hızını verir; grafikteki kesikli çizgi bu eğimi gösterir. Eksik yıllar çizgide birleştirilmez.", "Korelasyon nedensellik kanıtı değildir; sonuçları veri dönemi, kaynak ve doğal değişkenlikle birlikte yorumlayın."],
    },
    {
      title: "Harita araçları ve modlar",
      body: "Bir ülke adı yazmadan arama yapabilir veya Draw Mode ile doğrudan bir koordinata tıklayabilirsiniz.",
      points: ["Layer Gallery görsel katmanı seçer; sayısal trend ayrı NASA/Google Earth Engine zaman serisinden hesaplanır. Global Story başlangıç ve seçili yılı karşılaştırır.", "Cascade yıllık seriler arasındaki gecikmeli korelasyonu ölçer; neden-sonuç kanıtlamaz. Global Story'deki GBIF kayıtları hayvan sayısı değildir.", "Impact, backend ve Earth Engine yapılandırılmışsa WorldPop/VIIRS maruziyet bağlamı sağlar; bağlantı yoksa hata durumunu gösterir, veri uydurmaz."],
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
      title: "Blue does not always mean cold",
      body: "A color's meaning depends on the selected layer.",
      points: ["The satellite basemap is aerial imagery; capture dates vary by region, and house-level detail is not available everywhere.", "In the Temperature layer, blue means lower and yellow-red means higher surface temperature.", "NDVI, soil moisture, and GRACE each use different scales and units. Color does not mean increase/decrease or good/bad."],
    },
    {
      title: "Year selection and data coverage",
      body: "The timeline changes the selected satellite observation year. The layer badge identifies the variable and year currently requested.",
      points: ["Similar years can have similar colors even when the underlying observations differ.", "GRACE V04 ends in January 2017, so annual analysis stops at the last complete year, 2016. Later selected years display the available coverage clearly.", "The satellite basemap capture date may differ from the selected year; the timeline changes thematic measurements and the analysis period."],
    },
    {
      title: "p-value and Sen's slope",
      body: "Read the annual time series, Sen slope line, and statistical evidence together.",
      points: ["The p-value measures evidence against a no-trend assumption. p<0.05 is statistical evidence; it is not a 95% probability that the trend is true.", "Sen's slope estimates the median annual rate of change; the dashed chart line shows that slope. Missing years are not connected in the observed series.", "Correlation is not proof of causation; interpret results with the period, source, and natural variability in mind."],
    },
    {
      title: "Map tools and modes",
      body: "Search for a place or click a coordinate directly with Draw Mode; no country name is required.",
      points: ["Layer Gallery selects a visual layer; numerical trends come from a separate NASA/Google Earth Engine time series. Global Story compares baseline and selected years.", "Cascade measures lagged correlation between annual series; it does not prove cause and effect. GBIF records in Global Story are not animal counts.", "Impact provides WorldPop/VIIRS exposure context when the backend and Earth Engine are configured; without them, the app reports unavailability instead of inventing data."],
    },
    {
      title: "When can you export a PDF?",
      body: "Report buttons activate only when a verified satellite-data series is sufficient for a report.",
      points: ["Reports include the source, product ID, coordinates, unit, and annual observation count.", "At least 8 valid annual observations are required, and the series must cover the selected end year.", "Using NASA data does not make a statistical conclusion perfect or 100% certain; uncertainty is stated in the report."],
    },
  ];

  function finishTour() {
    localStorage.setItem("twinearth-guide-v1", "complete");
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
