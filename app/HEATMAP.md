# Geçmişe dayalı ek kapasite ihtiyacı

Haritadaki **Isı haritası** düğmesi son 14 günlük dolma hızını gösterir.
Anlık doluluk, doluluk filtresi, seçilen gelecek saati ve rota kararları bu
katmanın hesabına girmez. Veri kaynağı filtresi canlı/simülasyon kapsamını seçer.
Noktalarda mevcut doluluk ve gelecek merceğinde tahmin gösterilmeye devam eder.

Kod güncellendiğinde çalışan Python backend de yeniden başlatılmalıdır; eski
işlem yeni analiz alanını kendiliğinden yüklemez. Arayüz bu durumu gerçek geçmiş
yetersizliğinden ayırır ve backend yeniden başlatma uyarısı gösterir. PWA'da
"Yeni sürüm hazır → Yenile" ile yeni uygulama kabuğuna geçilir.

## Hesap

- Yalnız `ok` kaliteli, 0–100 aralığındaki geçmiş seviyeler kullanılır.
  Canlı veride ayrıca RF kaynağı, mevcut kalibrasyon ve sıralı kayıt gerekir.
- SQLite geçmişi 15 dakikalık ortalamalara indirger; paket sıklığı ağırlık değildir.
  Tamamen geçersiz zaman dilimleri boş kalır. Gelecek kayıtlar kullanılmaz.
- 30 dakikayı aşan boşluklar, 20 puanı aşan seviye düşüşleri ve kayıtlı toplama
  olayları dolum dönemlerini ayırır. En az 45 dakikalık dört örnekli sürekli
  parçaların net pozitif artışı toplanır; küçük gürültü artışları tek tek toplanmaz.
- Hız = toplam net artış / bu parçaların gözlenen saati (yüzde puan/saat).
  En az 24 saat zaman aralığı, 12 saat gözlem, %40 zaman kapsamı gerekir;
  son güvenilir gözlem 48 saatten eskiyse gösterge kullanılamaz.
- 180 metre çevrede Gaussian ağırlıklı **ortalama** hız çizilir. Ağırlık,
  uzaklık ve mevcut nominal kutu kapasitesidir. Böylece çok sayıda yavaş dolan
  kutu tek başına sıcak bölge oluşturmaz. Bu servis sınırı veya doğrulanmış
  şehir modeli değildir; örnek bulunmayan alanlar şeffaftır.
- Sabit renk ölçeği: 0 mor → 1,6 mavi → 3,2 yeşil → 4,8 sarı → 6,4 turuncu →
  8 ve üzeri kırmızı. Kamera/zoom, filtredeki en büyük değer veya kutu sayısı
  renk eşiğini değiştirmez. Eşikler MVP sunum varsayımıdır, mevzuat standardı değildir.

Kırmızı alan ek kapasite veya daha sık toplama için öncelikli inceleme demektir.
Kesin ilave kutu adedi hesaplanmaz: bunun için toplama aralığı, kutu tipi ve
saha uygunluğu da gerekir. Seviye yüzdesi gerçek atık hacmi/ağırlığı değildir.
Tam dolu bekleme sürelerinde gizli talep ölçülemez; hız ihtiyacı düşük gösterebilir.
Bu süreler kutu ayrıntısında belirtilir. Veri olmayan yer düşük talep sayılmaz.

## Performans ve uyumluluk

Geçmiş hesabı canlı kutuda beş dakika, simülasyonda veri değişene kadar bellekte
tutulur. Canlı geçmiş SQLite içinde gruplanır. Yüzey en uzun kenarı 320 piksel
olan sabit Mercator koordinatlı bir görüntüdür. Yalnız katman açıkken, konum veya
tarihsel hız değişince üretilir; sürükleme/zoom/zaman merceğinde yeniden hesaplanmaz.
MapLibre görüntü katmanı binaların ve rota çizgisinin altındadır; Leaflet yedekte
aynı görüntü coğrafi overlay olarak kullanılır. PWA uygulama kabuğu sürümlenmiştir.

Mevcut simülasyonun 14 günlük geçmişi hızlı/yavaş örneklerini sağlar; gerçek belediye
talebi veya mekânsal davranış doğrulaması değildir. H1 yeterli gerçek geçmiş birikene
kadar ısı hesabına alınmaz. Tarihsel mock raporlar önceki sürümün denetimidir.

Görselleştirmede [MapLibre image source](https://maplibre.org/maplibre-style-spec/sources/#image)
kullanılır. [QGIS KDE belgesi](https://docs.qgis.org/3.40/en/docs/user_manual/processing_algs/qgis/interpolation.html#heatmap-kernel-density-estimation)
yarıçap/ağırlık etkisini açıklar; burada nokta yoğunluğu yerine kapasiteye göre
normalize edilmiş ortalama hız kullanılması ürünün ek kapasite amacına yönelik tasarım kararıdır.

Kontrol:

```powershell
python -m unittest discover -s app/tests -q
node app/tests/test_demand.cjs
node app/tests/test_future_pwa.cjs
```
