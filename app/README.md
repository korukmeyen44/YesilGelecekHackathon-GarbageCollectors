# Garbage Collectors operasyon merkezi

KTÜ Kanuni Kampüsü çevresinde tek araçla toplama kararı veren yerel hackathon MVP'si.
36 simüle kutu, 14 günlük üretilmiş geçmiş ve 1 fiziksel sensör yuvası içerir.
Gerçek cihaz kayıtları ve simülasyon farklı SQLite dosyalarında tutulur.

## Uydu, 3D şehir ve şoför kokpiti

Harita, yerel olarak paketlenmiş **MapLibre GL JS 5.6.2** kullanır. Aynı harita
üzerinde uydu görüntüsü, low-poly şehir ve yol haritası arasında geçiş yapılır.
Kutu renkleri, doluluk yüzdeleri, seçim paneli, filtreler, numaralı duraklar ve
backend'in hesapladığı rota korunur. Son sefer genel bakışta da görünür.

- **Uydu:** Esri World Imagery; internet gerekir. Bina katmanı uydu üzerine de açılabilir.
  Servis hatasında yerel şehir görünümüne geçilir.
- **Binalar:** zeminden bağımsız aç/kapat. Kampüste 328, Ortahisar/Meydan, Kalkınma
  ve Konaklar çevresinde 7.916 ek bina; toplam 8.244 gerçek OSM tabanı. 8.237
  yükseklik kat × 3 m veya 12 m tahminidir. Fotogrametri değildir.
- **3D / 2D düğmesi:** aynı düğmeyle kamera eğimi değişir; zemin ve bina seçimi korunur.
- **Dönüş:** sağ fare tuşuyla sürükleme, Shift + yön tuşları, dokunarak iki parmak
  döndürme veya haritadaki sağ/sol/kuzey düğmeleri. **Arazi:** isteğe bağlı Mapzen/AWS yükseklikleri.
- **Bölge seçimi:** Kampüs, Meydan, Kalkınma ve Trabzon geneli için kamera konumları;
  harita bu sınırların dışına gezinmeyi engellemez.
- **Doluluk ısısı:** yalnız bilinen güncel dolulukla ağırlıklandırılır. Zamana
  bağlı yoğunluk analizi veya geleceğin tahmini değildir. Belirsiz ölçüm katılmaz.
- **Uçuş:** plan duraklarını veya kutuları dolaşır. Sürükleme, sekmenin gizlenmesi
  ve tekrar basma durdurur. Varsayılan olarak azaltılmış hareket tercihine uyar.
  Diğer seçenekler → Sunum animasyonları bu sekmede kullanıcı tercihiyle hareketi açar.
- **Bildirimler:** kapatma düğmesi ve 8 saniyelik zaman çubuğu. Üzerine gelince
  veya klavye odağı bildirimdeyken sayaç duraklar.
- **Diğer seçenekler:** ışık, PNG, Leaflet 2D yedek. Yedekte rota, renk ve kutu
  seçimi çalışır; 3D'ye dönmek için sayfa yenilenir.
- **Tam ekran:** haritayı büyütür; tarayıcı izin vermezse sayfa içi tam ekran açar.

### Şoför modu

Rota planlama → sefer oluştur → **Şoför modunu aç**. Mevcut harita tam ekran
kokpite dönüşür. Sıradaki durak, rotada kalan mesafe, durak inceleme düğmeleri,
araç işareti ve kameranın aracı izlemesi bulunur. Yol verisindeki OSRM manevraları
varsa yaklaşan dönüş gösterilir; yaklaşık rotada dönüş talimatı uydurulmaz.
Önceden kaydedilmiş planlarda manevra yoksa yeni plan oluşturun.

**Demo sürüşü**, 150 saniyede rotayı görselleştiren simülasyondur; araçtan gelen
konum veya hız değildir. **GPS başlat**, kullanıcının tarayıcı izniyle gerçek
cihaz konumunu izler. Konum backend'e veya analitik hizmetine gönderilmez.
HTTPS veya aynı cihazda localhost gerekir; telefonun HTTP yerel IP bağlantısında
GPS tarayıcı tarafından engellenebilir. 60 m üzeri belirsizlikte ilerleme
hesaplanmaz. Rota dışına çıkma uyarısı vardır; otomatik yeniden rota yoktur.
Durak ileri/geri düğmeleri inceleme içindir, toplama kaydı oluşturmaz. Kamera
elle sürüklendiğinde takip durur; **Aracı takip et** tekrar açar. GPS, duraklatma,
çıkış ve sekme gizlenmesinde kapatılır. Sefer değişirse eski kokpit kapanır.

OSRM **otomobil profili** kullanılır: kamyon yüksekliği, ağırlığı, yol erişim
kısıtları ve canlı trafik bilinmez. Saha kullanımı için kamyona uygun yol servisi
ve gerçek cihaz testleri gerekir. Bu sürüm hackathon rota takip prototipidir.

### Performans yaklaşımı

Tek WebGL bağlamı; en fazla 2 işçi; 8 paralel görsel isteği; 96 karo önbelleği.
DPR otomatikte masaüstü 1.5, mobil 1.25 ile sınırlıdır; ekonomik 1, keskin en
fazla 2. Kamera hareketindeki harita render aralıkları yavaşsa otomatikte DPR 1'e
harita boşta kaldığında iner; çözünürlük değişimi etkin fare hareketini kesmez. FPS etiketi render olaylarının örneklemidir; GPU süresi veya donanım
karşılaştırması değildir. Ekran boşta iken sürekli animasyon döngüsü çalışmaz.
Aynı rota/doluluk geometrisi her 5 saniyede yeniden GPU kaynağına gönderilmez;
işaretçiler ve odak korunur. Kalıcı `preserveDrawingBuffer` kapalıdır; PNG, tek
render sırasında kopyalanır. Demo araç/kamera güncellemesi en fazla 10 Hz'dir.

Bina kaynağı `web/data/scene-source.json` ve `web/data/LICENSE.md` içindedir.
OSM/Esri/AWS atıfları haritada korunur. Dış karolar topluca indirilmez.
Yerel kampüs verisini yenileme: `python app/tools/fetch_scene.py`.
Geniş Trabzon bina önbelleği: `python app/tools/fetch_scene.py --trabzon`.
Kaynak sınırları, indirme tarihi ve tahmini yükseklik sayısı `web/data/trabzon-source.json` içindedir.

### Mevcut demo verilerinin yükseltilmesi

Başlangıçta envanter sürümü 2’ye yükseltilir: S25–S36 adlı 12 yeni simülasyon
noktası eklenir. Mevcut 24 kutunun konumu, doluluğu, geçmişi, arıza durumu, elle
seçimi ve planları korunur; aynı yükseltme tekrar kayıt eklemez. Yeni kutular da
14 günlük geçmişle gelir. Fiziksel sensör kaynağı H1 olarak ayrı kalır. Arayüz
ve yeniden üretilmiş mock raporları sayıları güncel envanterden alır.

```powershell
node app/tests/test_map_scene.cjs
node app/tests/test_route_math.cjs
python -m unittest discover -s app/tests -q
```

Sözleşme testleri kamera/rota/işaretçi korumasını, tekrar veri gönderilmemesini,
GPS kalite kontrolünü ve temizliğini, sefer değişmesini ve rota projeksiyonunu
sınar. OSRM manevra ayrıştırması ve önbelleği Python testleriyle doğrulanır.
Görsel kontrol ve sınırlar `reports/HARITA_DOGRULAMA.md` dosyasındadır.

## Başlatma

Repo kökünde Python 3.10 veya üzeriyle:

```powershell
python -m app.server
```

**http://127.0.0.1:8080** adresini açın. Sunucuyu durdurmak için Ctrl+C kullanın.
Ek Python/npm bağımlılığı yoktur. Leaflet 1.9.4 dosyaları lisansı ile `web/vendor`
içindedir. Uydu zemini Esri, yol zemini OSM ve rota verisi OSRM kaynaklıdır. Bunlar için
internet gerekir; zemin gelmezse noktalar ve diğer ekranlar kullanılabilir.

Yol servisine hiç istek yapmadan çalıştırmak için:

```powershell
python -m app.server --offline
```

Bu durumda mesafe kuş uçuşudur, süre varsayılan hızdan hesaplanır ve çizgiler
kesiklidir. Bunlar sürüş güzergâhı veya doğrulanmış sürüş mesafesi değildir.
`--offline` yalnız backend yol servisini kapatır; tarayıcı harita zemini için
normalde OSM'ye erişmeye çalışır. Harita karoları topluca indirilmez.

## Gerçek sensörü bağlama

1. `firmware/README.md` içindeki gerçek kutu kalibrasyonunu tamamlayın.
   `calibration.local.json` varsa sunucu otomatik seçer. Yoksa güvenli örnek
   kalibrasyon kullanılır ve gerçek doluluk uydurulmaz.
2. Mevcut collector HTTP sunucusunu aynı portta ayrıca çalıştırmayın. Bu uygulama
   aynı `POST /api/telemetry` ve `GET /api/latest` sözleşmesini sağlar.
3. USB köprüsünü aynı şekilde başlatın; COM portunu değiştirin:

```powershell
./firmware/.tools/venv/Scripts/python.exe firmware/tools/serial_bridge.py --port COM5
```

Gateway HTTP kullanıyorsa URL'si bilgisayarın yerel IP'sinde `/api/telemetry`
olmalı. Yerel ağa açmak için açıkça:

```powershell
$env:GC_API_TOKEN = 'yerel-demo-icin-ascii-anahtar'
python -m app.server --host 0.0.0.0
```

Aynı anahtarı köprü/gateway'e girin. Panel anahtarı sorar; yalnız sekme belleğinde
tutar. Bu yerel ağ MVP'sidir; HTTP şifrelenmez ve internete açık dağıtım için
tasarlanmamıştır. Varsayılan dinleme adresi yalnız `127.0.0.1`'dir.

Mevcut fiziksel kayıtları kullanmak için:

```powershell
python -m app.server --config firmware/config/calibration.local.json --hardware-db firmware/.build/hardware.sqlite3
```

Varsayılan yeni fiziksel veritabanı `app/.data/hardware.sqlite3`, uygulama ve
simülasyon deposu `app/.data/operations.sqlite3` olur. Bu dosyalar Git dışındadır.
Yeni kalibrasyondan önceki farklı kalibrasyonlu geçmiş tahmine katılmaz.
`source=simulator` telemetrisi canlı girişte reddedilir; eski firmware simülatörü
yalnız kendi collector test akışı içindir. Uygulamanın demosu Demo kontrolü üzerinden
çalışır. `config.json` içindeki `node_id`, ad ve koordinatlar gerçek kurulumla
eşleştirilmelidir. Sunucuyu yeniden başlatınca dosya tekrar okunur.

## Ekranlar ve karar kuralları

- **Genel bakış:** kaynak/doluluk filtreli harita, kutu arama, öncelik listesi,
  grafik, ölçüm kalitesi, gerekçeler ve tahminler.
- **Rota planlama:** demo/canlı kaynak seçimi; doluluk eşiği, sonraki ziyarete
  kadar eşik riski ve azami toplama aralığıyla aday seçimi; elle ekle/çıkar;
  kapasite ve sefer süresi sınırları; numaralı duraklar ve varış süreleri.
- **Sensör sağlığı:** eski veri, geçersiz/kısmi ölçüm, kalibrasyon ve ortak gateway
  bağlantı uyarıları. Aynı durum tek satırda gösterilir; fiziksel neden teşhis edilmez.
- **Etki analizi:** tek seferlik referans karşılaştırması; mesafe, süre, yakıt
  maliyeti ve yakıt yanmasından kaynaklı CO₂ tahmini. Birikimli saha tasarrufu değildir.
- **Demo kontrolü:** yalnız simülasyon zamanı +15 dk / +1 saat / +4 saat ilerler;
  seçilen simüle kutuya bağlantı/ölçüm sorunu uygulanır.
- **Operasyon ayarları:** eşikler, sonraki ziyaret, azami toplama aralığı, hizmet
  süresi, hacim kapasitesi, sefer süresi, tüketim, yakıt fiyatı, CO₂ katsayısı ve
  kısmi kaliteli verinin planlamada kullanılması ayarlanabilir.

Harita renkleri sabit olarak %0–49 yeşil, %50–79 sarı, %80–100 kırmızıdır.
Toplama eşiği ayrı operasyon ayarıdır; renk eşiği değişmez. Bilinmeyen veri gridir.
Hızlı dolum işareti saatte en az 6 yüzde puan olan ayarlanmış demo kuralıdır;
nedensel açıklama veya çevre kutularına ilişkin istatistiksel test değildir.

Mevcut firmware'in kabul ettiği yaklaşık yüzde kullanılır. `null` sıfıra çevrilmez.
Eski/geçersiz/kalibrasyonsuz kutu otomatik olarak planlanmaz. Operatör elle
eklerse kapasite hesabı için tam nominal kutu varsayılır. Kısmi kaliteli ölçümün
otomatik planlamaya katılması varsayılan olarak kapalıdır.

## Rota ve karşılaştırma sınırları

OSRM otomobil profiliyle yönlü süre/mesafe matrisi ve rota geometrisi alınır.
Kamyona özel yükseklik, ağırlık, dar sokak erişimi veya canlı trafik doğrulanmaz.
Yol matrisi ve rota geometrisi koordinatlara göre yerel depoda önbelleğe alınır;
geçmiş planın veri zamanı ve varsayımları korunur. İstendiğinde yol ağı seçeneği
kapatılarak açıkça yaklaşık hesap yapılabilir. Yol geometrisi alınamazsa çizgi
şematik ve kesikli gösterilir; yol matrisi varsa hesaplanan mesafe korunur.

Çözücü en yakın komşu + yönlü 2-opt kullanır ve sabit sıralı çözümü de karşılaştırır.
Kesin optimum garantisi yoktur. Öncelik sırasıyla kapasite/süreye sığan kutular
alınır; sığmayanlar ve elle dışlanan kritik kutular açıkça raporlanır. Gelişmiş
çok araçlı VRP, zorunlu boşaltma tesisi ve çalışma molaları ilk sürümde yoktur.

Referans, tüm kullanılabilir kutuların kimlik sırasıyla gezildiği demo senaryosudur;
gerçek belediye rotası değildir. Aynı depo, matris ve durak süresi kullanılır.
Referans aynı araç kapasitesi veya süre sınırına sığmıyorsa tasarruf hesaplanmaz.
Ziyaret azaltımını içeren tek seferlik fark ile **aynı duraklarda sıralama etkisi**
ayrı gösterilir. Ertelenen hizmetin gelecekteki maliyeti toplam farkta yoktur.
Çıktı ayrıca ertelenen kritik adayları ve varış öncesi tahmini doluluk riskini gösterir.

Yakıt = km × L/100 km / 100; maliyet = yakıt × ₺/L; CO₂ = yakıt × kg CO₂/L.
Başlangıç değerleri 35 L/100 km, 50 ₺/L ve 2,68 kg CO₂/L **demo varsayımıdır**;
güncel fiyat, ölçülmüş filo tüketimi veya Türkiye'ye özgü doğrulanmış katsayı değildir.
Rölanti/dur-kalk/eğim/yük ayrıca modellenmez; personel ve bakım gideri yoktur.
Yöntem kaynağı: [EPA SmartWay](https://www.epa.gov/sites/default/files/2021-01/documents/420b21002.pdf).

Plan kayıtları kalıcıdır. Aynı istek kimliği aynı planı döndürür. Plan tamamlaması
tekrarlandığında ikinci toplama kaydı oluşmaz. Girdiler değişirse eski plan
demo planı tamamlanamaz; yeniden planlamak gerekir. Canlı seferde değişen telemetri,
operatörün yapılmış toplama için kayıt oluşturmasını engellemez. Demo tamamlama seviyesi %5 yapar;
fiziksel kutuda yalnız operatör kaydı oluşturulur, gerçek telemetri değiştirilmez.

## Dolum tahmini ve değerlendirme

Mevcut mock verinin kapsamını ve jüriye gösterilecek grafikleri üretmek için:

```powershell
python -m pip install -r app/requirements-analysis.txt
python -m app.mock_report
```

Bu araç mevcut `app/.data/operations.sqlite3` dosyasını salt okunur açar; yeni
veri üretmez, demo veya donanım kayıtlarını değiştirmez. `app/reports` altında
internet gerektirmeyen tek HTML raporu, sunuma uygun PNG, sayısal JSON ve inceleme
notu oluşturur. HTML dosyasını doğrudan tarayıcıda açabilirsiniz. Rapor bir anlık
görüntüdür; demo verisi değişince yeniden üretilmelidir. İsteğe bağlı Matplotlib
yalnız rapor üretiminde gerekir; uygulama sunucusu ek bağımlılık istemez.

14 günlük mevcut veri operasyon demosuna uygundur; haftalık davranış, geçmiş
kesintiler ve bölgesel yoğunluk süreci açısından sınırlıdır. Rapordaki zaman ×
kutu ısı matrisi coğrafi yoğunluk heatmap'i değildir. Ayrıntılı bulgular ve sonraki
veri üreticisi önerileri `reports/MOCK_VERI_INCELEMESI.md` içindedir.
Üreticiye ilişkin yorumlar incelenen `storage.py` sürümüne özeldir; üretici kodu
değiştirildiğinde bu kapsam değerlendirmesi de güncellenmelidir. Rapor sayısal
anlık görüntünün ve üretici kaynağının SHA-256 özetlerini saklar.

Son 6 saatteki geçerli ölçümler 5 dakikalık medyanlara özetlenir. En az 45 dakikaya
yayılan 4 örnek aranır. Son boşaltma/büyük düşüş sonrası dönem kullanılır;
bir saati aşan veri boşlukları birleştirilmez. Nokta çiftlerinin eğimlerinin medyanı
(Theil–Sen) dolum hızını verir. Pozitif hız varsa toplama ve tam doluluk eşiklerine
kalan süre hesaplanır. Eğimlerin %20/%80 yüzdeliklerinden elde edilen aralık
**hız duyarlılığıdır**, kalibre edilmiş %80 güven/tahmin aralığı değildir.

Sentetik geçmiş üzerinde geçmişten geleceğe ilerleyen değerlendirme:

```powershell
python -m app.backtest
```

Son 3 günde saatlik başlangıçlar; yalnız o anda bilinebilen geçmiş. Bir saatlik
doluluk hatası sabit son değer tahminiyle karşılaştırılır; 4 saatlik uyarıların
doğru/yanlış/kaçırılan sayıları ve gözlenen eşik zamanlarının hatası raporlanır.
Boşaltma içeren bir saatlik doluluk pencereleri ayrı tutulur. Üretici ile modelin
benzer eğilimleri olması sonucu iyimser yapabilir. Gerçek sensörde doğruluk
iddiası için uzun süreli saha verisi gerekir.

## Sunum akışı

1. Genel bakışta 36 simülasyon ve 1 gerçek sensör yuvasını gösterin.
2. S03'ü açın: orta doluluğa rağmen hızlı dolum nedeniyle aday olduğunu açıklayın.
3. Rota planlamada demo rotası oluşturun; haritada sıralı durakları gösterin.
4. Sabit referans ve aynı duraklarda sıralama etkisini ayrı anlatın.
5. Etki analizinde varsayımları gösterin; saha tasarrufu olmadığını belirtin.
6. Demo kontrolünde +1 saat ilerletin: erken uyarı ve yeniden planlama ihtiyacını gösterin.
7. Bir kutunun bağlantısını kesin ve sağlık panelini gösterin.
8. Canlı kutuya fiziksel hedef ekleyin: ölçüm kabul edilince arayüz güncellenir.
9. Yeni planı tamamlayın; yalnız simülasyon kutuları boşalır ve yeni dolum dönemi başlar.

Canlı kutuda birkaç dakikalık demo geçmişinden saatlik tahmin uydurulmaz.
Sunum yeniden denenecekse eski demo kaydını silmek yerine farklı veri klasörü seçin:

```powershell
python -m app.server --data-dir app/.data/prova-02 --port 8081
```

## Testler

```powershell
python -m unittest discover -s app/tests -v
python -m unittest discover -s firmware/tests/python -v
node --check app/web/app.js
```

Uygulama testleri kaynak ayrımı, eksik/eski veri, tahminde gelecek veri sızıntısı,
boşaltma ve veri boşlukları, kapasite/süre sınırları, yönlü rota, idempotent
işlemler, değişen plan girdileri, HTTP kimlik doğrulaması ve telemetri uyumunu kapsar.
Gerçek donanım doğruluğu bu testlerle kanıtlanmaz. Firmware'in C++/fiziksel testleri
kendi klasöründe ayrıca tarif edilmiştir.

## API

| Yöntem | Yol | İşlev |
| --- | --- | --- |
| GET | `/api/dashboard` | Kutu durumları, uyarılar, ayarlar, son plan |
| GET | `/api/bins/S03` | Ayrıntı, 48 saatlik geçmiş, toplama olayları |
| GET | `/api/latest` | Firmware alıcısıyla uyumlu fiziksel son durum |
| POST | `/api/telemetry` | Yalnız `source=rf` fiziksel v2 paket |
| POST | `/api/override` | `{bin_id, mode: auto/include/exclude}` |
| POST | `/api/settings` | Değiştirilecek ayarlar |
| POST | `/api/plan` | `{scope: demo/live, online, request_key}` |
| POST | `/api/plan/complete` | `{plan_id}` |
| POST | `/api/collection` | `{bin_id, request_key}` |
| POST | `/api/demo/advance` | `{hours: 0.25/1/4}` |
| POST | `/api/demo/fault` | `{bin_id, fault: normal/offline/unstable/degraded}` |

Uygulama `GC_API_TOKEN` ayarlıysa tüm API çağrılarında Bearer anahtarı ister.
Arayüz dosyaları anahtar içermez. Farklı Origin'den yazma istekleri reddedilir.

## Açık kaynak bileşenler ve veri hizmetleri

- [MapLibre GL JS 5.6.2](https://maplibre.org/maplibre-gl-js/) · BSD-3-Clause · `web/vendor/MAPLIBRE-LICENSE`
- [Esri World Imagery](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer) · canlı karo servisi, kaynak atfı haritada
- [Leaflet 1.9.4](https://leafletjs.com/) · BSD-2-Clause · lisans `web/vendor/LEAFLET-LICENSE`
- [OpenStreetMap](https://www.openstreetmap.org/copyright) · haritada atıf korunur
- [OSM karo kullanım politikası](https://operations.osmfoundation.org/policies/tiles/)
- [OSRM API](https://project-osrm.org/docs/v5.24.0/api/) · kamusal demo servisinin erişilebilirliği garanti değildir
- [Zaman serisi doğrulaması](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation)
