# Tek ortalama protokolü ve ölçüm algoritması

## Sürüm ve amaç

Bu belge protokol v2'yi tanımlar. İki sensörün ayrı mesafeleri kutu firmware'inde aritmetik ortalamaya dönüştürülür. Bilgisayar tek ortalama mesafeyi kalibre ederek yaklaşık doluluk hesaplar. V1'in iki mesafe/medyan düzeni bu sürümde kullanılmaz; bütün uçlar birlikte güncellenmelidir.

## Grup büyüklüğü ve zamanlama

Bir grup 10 çift, toplam 20 okuma girişimidir. Sensörler dönüşümlü tetiklenir. Grubun ilk okumasından önce ve her sonraki okumadan önce, önceki okuma tamamlandıktan itibaren 425–575 ms dahil rastgele beklenir. İki tetikleme aynı anda yapılmaz. Kutuların başlangıcı kutu kimliği ve rastgele sapmayla ayrılır; ayrı kutular arasında merkezi akustik zamanlama yoktur.

Beklemelerin beklenen toplamı `20 × 500 = 10000 ms` olur. Alt/üst sınır `8500–11500 ms` olup yankı süreleri ve döngü yükü buna eklenir. Zamanlama gecikirse ölçümler peş peşe hızlandırılarak telafi edilmez. RF gönderiminden sonra yeni grup başlar; önceki 3 saniyelik ek bekleme kaldırıldı. RF tekrarları rapor aralığını uzatabilir. Gerçek grup süresi pakette bulunur. 60 saniyeyi aşmış grup atılır ve yeni gruba geçilir.

Ses hızı 343 m/s varsayılır; sıcaklık telafisi yoktur. Mesafe mm cinsindedir; bu birim saha doğruluğu iddiası değildir. Alt sınır 20 mm, yapılandırılmış üst sınır varsayılan 1200 mm'dir. Yankı okuması bu üst sınıra göre yaklaşık 8 ms zaman aşımıyla sınırlandırılır.

## Aritmetik ortalama ve geçerlilik

Her çifti oluşturan iki okumadan biri geçersizse çift ortalamaya katılmaz. Sensörlerin eşit ağırlığını korumak için tek geçerli sensörle çift oluşturulmaz. Geçersiz okumalar sıfır veya boş kutu mesafesi olarak kullanılmaz. Geçersiz denemeler de sabit 10 deneme sınırına dahildir.

```text
ortalama_mesafe = geçerli çiftlerdeki (sensör1 + sensör2) toplamı / (2 × geçerli çift sayısı)
```

Toplam 32 bit tutulur; yalnız son sonuç en yakın mm'ye yuvarlanır. Önce çiftleri yuvarlayıp tekrar ortalamak kullanılmaz. En az 6 geçerli çift gerekir. Grup yayılımı, en büyük ve en küçük çift ortalamaları arasındaki farktır; yarım mm farklar muhafazakâr biçimde yukarı yuvarlanır. Yayılım 80 mm'yi aşarsa grup `unstable` olur. Bu, aynı grupta zaman içinde değişimi denetler; iki sensörün birbirinden farklı mesafesini doğrudan reddetmez.

| Durum kodu | JSON durumu | Koşul |
| --- | --- | --- |
| 0 | `ok` | 10 geçerli çift ve yayılım en fazla 80 mm |
| 1 | `too_few` | 6'dan az geçerli çift; kabul edilmiş mesafe yok |
| 2 | `unstable` | En az 6 geçerli çift fakat yayılım 80 mm'den büyük; mesafe yok |
| 3 | `degraded` | 6–9 geçerli çift ve yayılım en fazla 80 mm |

Hata maskeleri sensör başına korunur: 1 timeout, 2 alt mesafe sınırının altında, 4 üst mesafe sınırının üzerinde, 8 tetikleme öncesinde Echo HIGH. Maskeler bit düzeyinde birleştirilir. İki ayrı sensör mesafesi veya sensörler arası fark gönderilmez. Bu nedenle bilgisayar v2'de `sensor_disagreement` üretemez.

## RF paket biçimi

Paket tam 32 bayttır. Çok baytlı alanlar little-endian kodlanır; struct bellek görüntüsü gönderilmez.

| Ofset | Bayt sayısı | Alan |
| --- | --- | --- |
| 0 | 2 | ASCII `GC` |
| 2 | 1 | Sürüm 2 |
| 3 | 1 | Kutu kimliği 1–3 |
| 4 | 4 | Kalıcı açılış kimliği, sıfır hariç |
| 8 | 4 | Grup/mesaj sayacı; tekrar gönderiminde aynı kalır |
| 12 | 4 | Grubun bittiği Uno `millis()` değeri |
| 16 | 2 | Tek kabul edilmiş ortalama mesafe, mm |
| 18 | 2 | Çift ortalamalarının zamansal yayılımı, mm |
| 20 | 2 | Gerçek grup süresi, ms; 1–60000 |
| 22 | 1 | Denenen çift sayısı, daima 10 |
| 23 | 1 | Geçerli çift sayısı, 0–10 |
| 24 | 1 | Sensör 1 geçerli okuma sayısı, 0–10 |
| 25 | 1 | Sensör 2 geçerli okuma sayısı, 0–10 |
| 26 | 1 | Grup durumu |
| 27 | 1 | Sensör 1 hata maskesi |
| 28 | 1 | Sensör 2 hata maskesi |
| 29 | 1 | Ayrılmış alan; sıfır olmalı |
| 30 | 2 | İlk 30 bayt için CRC-16/CCITT-FALSE |

Kabul edilmemiş mesafe `65535`, JSON'da `null` olur. Hiç geçerli çift yoksa yayılım da aynı işaretle taşınır. Sensör örnek sayıları çift sayısıyla tutarlı olmalı; başarısız okuma olan sensörün hata maskesi sıfır olmamalıdır. V1 paketler sürüm kontrolünde reddedilir. RF CRC/ACK ve uygulama CRC'si kimlik doğrulaması veya şifreleme sağlamaz.

## Kimlik ve yeniden gönderim

Kutu + açılış + mesaj sayacı bilgisayarda tekil kimliktir. Uno ilk 288 EEPROM baytını 32 adet commit işaretli açılış kaydı için kullanır. Açılış sayacı ve bit tersi yazılır, commit en son yapılır. Doğrulanamayan yazmada gönderim durur. EEPROM silinmesi veya kart değiştirilmesi eski kimliklerle çakışabilir; bakımda veriyi arşivleyin veya kimlik politikasını güncelleyin.

RF otomatik ACK ve en fazla üç donanımsal yeniden deneme kullanır; bekleme ayarı kutuya göre farklıdır. Uygulama aynı paketi 50–199 ms rastgele beklemeyle en fazla üç kez göndermeyi dener. ACK yalnız radyo bağlantısına ilişkindir; bilgisayara kalıcı kayıt garantisi değildir. Bilgisayar aynı ölçümü ikinci kez eklemez; aynı kimlikle farklı ölçüm 409 olur. Eski sıra/açılış güncel durumu ilerletmez. Sayaç karşılaştırması 32 bit sarmayı destekler; yarım sayaç aralığından küçük fark varsayılır.

## Gateway ve JSON

USB, LCD ve HTTP ayrı görevlerdir; RF döngüsü bunların bitmesini beklemez. Çıkış kuyrukları 24 kayıttır; dolunca en eski kayıt düşürülür ve sayaç artar. HTTP kaydı gateway'de 30 saniyeyi aşarsa atılır. HTTP en fazla dört kez denenir; 408/429 dışındaki 4xx hatalarda tekrar yapılmaz. Kuyruklar RAM'dedir; güç kesilince kaybolur. I2C ekranı erişilemez olduğunda ekran güncellemeleri kapatılır.

JSON v2'de `sensors` dizisi yerine tek `measurement` nesnesi vardır:

```json
{"distance_mm":220,"spread_mm":4,"attempted_pairs":10,"valid_pairs":10,"valid_samples":[10,10],"status":"ok","error_masks":[0,0],"window_duration_ms":10000}
```

Bu nesne `version`, kutu/açılış/sıra, gateway kimlikleri ve yaş alanlarıyla aynı üst nesnede taşınır. `measured_uptime_ms` ve `received_gateway_ms` farklı cihazların çalışma süreleridir; UTC değildir. `age_ms` çıkış kuyruğunda geçen süreyi içerir; USB köprüsü kendi beklemesini de ekler. Bilgisayar yaklaşık gözlem sonunu `geliş zamanı − yaş` ile hesaplar. Grup içindeki en eski örnek yaklaşık bir grup süresi daha eskidir. RF/USB/ağ aktarım gecikmesinin tamamı bu yaşa dahil değildir.

## Bilgisayarda kalibrasyon ve zaman filtresi

Her kutu için tek `measurement.empty_mm` ve `measurement.full_mm` kalibrasyonu kullanılır. Referanslar sensörlerin son çapraz montajında firmware'in ürettiği ortalamadan ölçülmelidir. Eski iki sensörlü kalibrasyon dosyası v2 için reddedilir.

```text
doluluk = 100 × (boş_ortalama − ölçülen_ortalama) / (boş_ortalama − dolu_ortalama)
```

Kalibrasyon doğrulanmamışsa sonuç `uncalibrated` ve yüzde `null` olur. Boş referansı toleranstan fazla aşan mesafe `outside_geometry` sayılır; aksi durumda yüzde 0–100'e sınırlandırılır. Kısmi grubun `degraded` durumu korunur. Ayrı sensör doluluğu veya uyuşmazlığı hesaplanmaz.

Veri yaşı eşiği 35 saniyedir. Büyük doluluk değişikliği için mevcut üç ardışık grup doğrulaması korunur; yaklaşık 30 saniyelik doğrulama süreci oluşabilir. Geçersiz grup, sıra boşluğu, yeni açılış ve uzun veri arası aday sayacını sıfırlar. Kalıcı boşaltma da kabul edilir. Eski/geçersiz durumda güncel yüzde `null`; son kabul edilmiş yüzde ve yaşı ayrıca görünür. Kalibrasyon kimliği değişirse önceki güncel yüzde kullanılamaz.

Çapraz montaj veya ortalama, kararlı yanlış yüzey yankısını kesin olarak düzeltmez. Atık türü, kirlenmenin kesin nedeni, kapak açıklığı ve gerçek hacim bu veriden kesin belirlenemez. Pil voltajı bağlantısı ve deep sleep bu sürümde yoktur.

## Teknik kaynaklar

- [RF24 API](https://rf24.readthedocs.io/en/latest/classRF24.html): kanal hesabı, plus olmayan modüllerde 250 kbps kısıtı, ACK ve FIFO.
- [RF24 hata açıklamaları](https://github.com/nRF24/RF24/blob/master/COMMON_ISSUES.md): ACK kaybı ve güç kararlılığı.
- [HC-SR04 teknik belgesi](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf): nominal mesafe aralığı ve tetikleme prensibi.
- [Espressif HTTPClient kaynağı](https://github.com/espressif/arduino-esp32/blob/master/libraries/HTTPClient/src/HTTPClient.cpp): bağlantı/okuma zaman aşımı ve POST arayüzü.
- [BTK teknik ölçütleri](https://www.btk.tr/s3/web-btk-site/7708c26c-5161-4919-8b3d-daa31d4ac8fb/2026/05/66efd802-05a1-4dc7-94a7-80b740125b49.pdf): frekans ve cihaz kullanım koşulları. Sahaya çıkışta güncel koşullar ayrıca doğrulanmalıdır.

