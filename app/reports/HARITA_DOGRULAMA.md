# Trabzon haritası ve arayüz doğrulaması — 31 Ekim 2026

## Düzeltilen nedenler

1. `.scene-pin` için `position:relative`, MapLibre işaretçisinin `position:absolute`
   konumlandırmasını geçersiz kılıyordu. Eski sahne stil dosyası artık yüklenmiyor.
   Yeni dairesel işaretçilerin dış konumunu yalnız MapLibre yönetir; merkez ankrajı
   kullanılır. Kamera hareketleri verideki enlem/boylamı değiştirmez.
2. `dragstart` sırasında `Map.stop()` çağrısı etkin sürükleme işleyicisini de
   durduruyordu. Elle sürükleme artık yalnız uçuş zamanlayıcısını ve araç takibini
   iptal eder. Programatik dönme/eğim olayları uçuşu iptal etmez.
3. Düşük FPS'de çözünürlüğün etkin hareket sırasında değiştirilmesi de yeniden
   boyutlandırma yoluyla etkileşimi kesebilirdi. Otomatik kalite değişimi yalnız
   harita boşta kalınca uygulanır. Periyodik yenilemede ikinci merkezleme kaldırıldı.
4. Bina görünürlüğü zemin seçimine bağlıydı; iki seçim bağımsız hale getirildi.
5. Tarayıcının yerel tam ekrandan çıkması kokpiti beklenmedik biçimde kapatıyordu.
   Kokpit sayfa içi tam ekranda açık kalır; açık çıkış düğmesiyle kapatılır.
6. Azaltılmış hareket tercihi uçuşu engelliyordu. Tercih varsayılan olarak korunur;
   kullanıcı Diğer seçenekler → Sunum animasyonları ile bu sekmede hareketi açabilir.

## Tamamlanan özellikler

- Yuvarlak doluluk noktaları, ayrı durak rozetleri; 36 simülasyon + 1 fiziksel sensör yuvası.
- Uydu / Şehir / Yol zemini; bağımsız Binalar aç/kapat; tek 3D–2D geçiş düğmesi.
- Sağ fareyle ve dokunarak dönüş; sol/sağ/kuzey düğmeleri ve pusula.
- Kapatma düğmeli, 8 saniyelik zaman çubuklu bildirim; hover/odakta sayaç durur.
- Kampüs, Meydan, Kalkınma ve Trabzon geneli kamera konumları.
- 328 kampüs + 7.916 ek OSM bina tabanı = **8.244 bina**. 8.237 yüksekliğin
  kaynağı kat × 3 m veya 12 m tahminidir; 7'sinde doğrudan OSM height alanı vardır.
- Açık içerik alanı, koyu gezinme, okunur veri kartları ve tutarlı boşluklarla
  kurumsal arayüz; sağlık, etki, planlama ve ayrıntı ekranları aynı dili kullanır.

## Otomatik doğrulama

- **35 Python testi başarılı:** operasyon kuralları, kaynak ayrımı, fiziksel
  telemetri sözleşmesi, rota sınırları, manevra önbelleği ve envanter yükseltmesi.
- JavaScript sahne/kokpit ve rota matematiği testleri başarılı. Kontroller;
  sürüklemede stop çağrılmaması, programatik dönüşte uçuşun devam etmesi,
  zeminden bağımsız bina görünürlüğü, çift kamera merkezlemesinin engellenmesi,
  etkin harekette kalite değiştirilmemesi, GPS temizliği ve değişen planda
  kapanmayı kapsar. Bunlar gerçek GPS saha testi değildir.
- Yeni kutular mevcut demo deposuna bir kez eklenir. Mevcut doluluk, konum,
  geçmiş, arıza, elle seçim ve demo saati korunur; tekrar açılış kayıt çoğaltmaz.
- Mock raporları yeni 36 kutuluk anlık görüntüden salt okunur üretildi:
  **48.420 örnek**, 8 temel dolum hızı. Başlık ve hız frekansları artık envantere bağlıdır.

## Gerçek tarayıcıda kontrol

Ayrı demo deposuyla 8086 portunda çalışıldı; kullanıcının mevcut 8080 deposu bu
kontrol için sıfırlanmadı. Masaüstü 1440×1000 ve telefon 390×840 CSS görünümü incelendi.

- İki ardışık fare sürüklemesi ve yakınlaştırma/uzaklaştırma yapıldı.
  37 noktanın koordinatları aynen kaldı. İşaretçinin hesaplanan ekran merkezinden
  en büyük farkı yaklaşık **0,005 CSS pikseli** olarak gözlendi.
- 3D/2D geçişi, bina kapalıyken zemin değişimi ve uydu üzerine yeniden bina açılması çalıştı.
- Sunum hareketleri açılınca uçuş devam etti; fareyle sürükleme uçuşu durdurdu.
- Bildirim otomatik kapandı; kapatma düğmesi ayrıca denendi.
- Gerçek OSRM seferi: **14 durak, 618 geometri noktası, 83 manevra**.
  Durak tablosundaki 14 kimlik haritadaki 14 rozetle eşleşti.
- S03 karar gerekçesi ve geçmiş grafiği açıldı. Şoför demo sürüşü ilerledi,
  duraklatıldı ve kokpitten çıkıldı. Toplama kayıt sayısı **0** kaldı.
- Mobil sağlık ekranında 4 uyarı satırı ve etki ekranında 4 kart görüntülendi;
  belge genişliği 383 CSS pikseli, görünüm 390 piksel: yatay taşma yok.
- Kontrol anında uygulama konsolunda hata/uyarı kaydı görülmedi.

## Görseller

`screenshots/trabzon-desktop.jpg`, `trabzon-driver.jpg`, `trabzon-mobile-overview.jpg`,
`trabzon-mobile.jpg` ve `trabzon-meydan-3d.jpg` gerçek tarayıcı yakalamalarıdır.
Yüksek Windows ölçeğinde bazı geniş klip yakalamaları sabit öğeleri yanlış
birleştirebildiği için hatalı ara yakalamalar çıkarıldı. Ana ekran tüm görünümü kapsayan
kliple, kokpit doğrudan ekran yakalamasıyla kaydedilip görsel olarak incelendi.

## Kaynaklar ve sınırlar

- [MapLibre](https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/)
- [OSRM Route / StepManeuver](https://project-osrm.org/docs/v5.24.0/api/)
- [Esri World Imagery](https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer)
- [OpenStreetMap lisansı](https://www.openstreetmap.org/copyright)
- [IBM Carbon veri tablosu](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/specifications)
- [Atlassian boşluk sistemi](https://atlassian.design/foundations/spacing)

Bina veri sınırları ve indirme tarihi `web/data/trabzon-source.json` dosyasındadır.
Kaynak/ODbL atıfları korunur. Bu görünüm fotogrametri değildir. Binlerce model
kamera yakınındaki karolar halinde çizilir; tek WebGL bağlamı kullanılır.
FPS etiketi render aralığı örneklemidir; ölçülmüş GPU performans garantisi değildir.
Gerçek GPS izni/saha sürüşü bu oturumda denenmedi. OSRM otomobil profili kamyonun
boyut/ağırlık kısıtlarını ve canlı trafiği içermez.
