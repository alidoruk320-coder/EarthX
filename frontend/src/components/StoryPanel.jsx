export default function StoryPanel({
  stories,
  activeStory,
  playing,
  onStart,
  onClose,
  onTogglePlayback,
  year,
  language = "en",
}) {
  const progress = Math.max(0, Math.min(100, ((year - 2002) / 24) * 100));
  const isTurkish = language === "tr";
  const translations = {
    polar: { title: "Kutup Paradoksu", description: "Grönland ve Antarktika'daki zıt buz kütlesi sinyallerini zaman içinde izleyin." },
    pacific: { title: "Pasifik'in İki Yüzü", description: "Batı Pasifik ile Kuzey Amerika kıyısındaki deniz seviyesi değişimini karşılaştırın." },
    vegetation: { title: "Yeşeren Asya, Kuruyan Amazon", description: "İki bölgedeki zıt bitki örtüsü sinyallerini inceleyin." },
    cascade: { title: "Buzdan Okyanusa, Okyanustan Bitkiye", description: "Dünya sistemi değişimlerini adım adım takip edin." },
  };
  const storyTitle = (story) => isTurkish ? translations[story.id]?.title : story.title;
  const storyDescription = (story) => isTurkish ? translations[story.id]?.description : story.description;
  const stage = year < 2008
    ? (isTurkish ? "NE? Sinyal saptandı" : "WHAT? Signal detected")
    : year < 2014
      ? (isTurkish ? "NEREDE? Örüntü genişliyor" : "WHERE? The pattern expands")
      : year < 2020
        ? (isTurkish ? "NE KADAR? Değişimin büyüklüğü artıyor" : "HOW MUCH? The magnitude grows")
        : (isTurkish ? "ANLAMLI MI? Kanıt değerlendiriliyor" : "SIGNIFICANT? Evidence evaluated");

  return (
    <aside className="storyPanel">

      <div className="storyPanelHeader">

        <div>
          <div className="storyEyebrow">
            {isTurkish ? "DÜNYA SİSTEMİ HİKAYE MODU" : "EARTH SYSTEM STORY MODE"}
          </div>

          <h2>{isTurkish ? "Dünya Sistemi Hikaye Atlası" : "Earth System Story Atlas"}</h2>
          <p className="storyIntro">{isTurkish ? "Sinyalden anlamlılığa uzanan kanıt yolculuğu." : "A guided evidence trail from signal to significance."}</p>
        </div>

        <button
          className="storyClose"
          onClick={onClose}
        >
          ×
        </button>

      </div>

      {!activeStory ? (
        <div className="storyList">

          {stories.map((story, index) => (
            <button
              key={story.id}
              className="storyCard"
              onClick={() => onStart(story)}
            >

              <span className="storyNumber">
                0{index + 1}
              </span>

              <span className="storyCardContent">
                <strong>
                  {storyTitle(story)}
                </strong>

                <small>
                    {storyDescription(story)}
                </small>
              </span>

              <span className="storyArrow">
                →
              </span>

            </button>
          ))}

        </div>
      ) : (
        <div className="storyActive">

          <div className="activeStoryLabel">
            {isTurkish ? "HİKAYE OYNATILIYOR" : "PLAYING STORY"}
          </div>

          <h3>
            {storyTitle(activeStory)}
          </h3>

          <p>
            {storyDescription(activeStory)}
          </p>

          <div className="storyProgress">

            <div className="storyProgressYears">
              <span>2002</span>
              <strong>{year}</strong>
              <span>2026</span>
            </div>

            <div className="storyProgressBar">
              <div className="storyProgressFill" style={{ width: `${progress}%` }} />
            </div>

          </div>

          <button
            className="storyPlayButton"
            onClick={onTogglePlayback}
          >
            {playing ? (isTurkish ? "HİKAYEYİ DURAKLAT" : "PAUSE STORY") : (isTurkish ? "HİKAYEYİ OYNAT" : "PLAY STORY")}
          </button>

          <div className="storyStage"><span>{isTurkish ? "ŞİMDİ GÖSTERİLEN" : "NOW SHOWING"}</span><strong>{stage}</strong></div>

          <div className="storyQuestions">

            <div>
              <span>WHAT?</span>
              <strong>
                {isTurkish ? "Ne değişiyor?" : "What is changing?"}
              </strong>
            </div>

            <div>
              <span>WHERE?</span>
              <strong>
                {isTurkish ? "Nerede değişiyor?" : "Where is it changing?"}
              </strong>
            </div>

            <div>
              <span>HOW MUCH?</span>
              <strong>
                {isTurkish ? "Değişim ne kadar büyük?" : "How large is the change?"}
              </strong>
            </div>

            <div>
              <span>SIGNIFICANT?</span>
              <strong>
                {isTurkish ? "Trend istatistiksel olarak anlamlı mı?" : "Is the trend statistically significant?"}
              </strong>
            </div>

          </div>

        </div>
      )}

    </aside>
  );
}