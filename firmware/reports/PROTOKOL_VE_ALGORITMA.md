# Veri protokolü ve ölçüm algoritması

## Ölçüm penceresi

Uno, sensör 1 ve sensör 2'yi sırayla toplam 10 kez tetikler. Her okuma sonrası en az 70 ms bekler. Yankı okuması, yapılandırılan üst mesafeye göre hesaplanan ve varsayılan 1200 mm için yaklaşık 8 ms olan zaman aşımıyla sınırlandırılır. Yeni ölçüm, gönderim denemeleri bittikten 3000 + 100–599 ms sonra başlar. Tam pencere ve yeniden denemeler nedeniyle bu süre paketler arasındaki kesin süre değildir.

Ses hızı sabit 343 m/s kabul edilir. Mesafe milimetre cinsinden tam sayıya yuvarlanır. Sıcaklık telafisi yoktur; milimetre birimi milimetre düzeyinde saha doğruluğu iddiası değildir. Nominal alt sınır 20 mm, varsayılan üst sınır 1200 mm'dir.

Her sensörde geçerli mesafeler sıralanır. En az üç örnek gereklidir. Beş geçerli örnekte yayılım ikinci ve dördüncü değer arasındaki farktır; tek uç değerler bu yayılım hesabından çıkarılır. Üç/dört örnekte yayılım tüm geçerli aralıktır. Yayılım 80 mm'den büyükse `unstable` üretilir ve kabul edilmiş mesafe gönderilmez. Eşikler başlangıç ayarıdır; gerçek malzemelerle doğrulanmalıdır.

`valid_samples`, nominal aralıktaki yankı sayısıdır; tek başına doğru çöp yüzeyinin ölçüldüğünü kanıtlamaz. Sistem kararlı biçimde yanlış yüzeyi görebilir.

## RF paket biçimi

Tüm çok baytlı değerler **little-endian** olarak açıkça kodlanır. C++ struct bellek görüntüsü gönderilmez. Paket tam **32 bayttır**; iki taraf statik payload kullanır.

| Bayt ofseti | Uzunluk | Alan |
| --- | --- | --- |
| 0 | 2 | ASCII `GC` |
| 2 | 1 | Protokol sürümü: 1 |
| 3 | 1 | Kutu kimliği: 1–3 |
| 4 | 4 | Kalıcı açılış kimliği; sıfır kullanılmaz |
| 8 | 4 | Ölçüm sayacı; yeniden denemede değişmez |
| 12 | 4 | Ölçüm penceresi bitişindeki Uno `millis()` değeri |
| 16 | 2 | Sensör 1 kabul edilmiş mesafe, mm |
| 18 | 2 | Sensör 1 yayılım, mm |
| 20 | 1 | Sensör 1 geçerli örnek sayısı |
| 21 | 1 | Sensör 1 durumu |
| 22 | 1 | Sensör 1 örnek hata bitleri |
| 23 | 2 | Sensör 2 kabul edilmiş mesafe, mm |
| 25 | 2 | Sensör 2 yayılım, mm |
| 27 | 1 | Sensör 2 geçerli örnek sayısı |
| 28 | 1 | Sensör 2 durumu |
| 29 | 1 | Sensör 2 örnek hata bitleri |
| 30 | 2 | İlk 30 baytın CRC-16/CCITT-FALSE değeri |

Mesafe için `65535` geçersiz işaretidir; JSON'da `null` olur. Hiç geçerli örnek yoksa yayılım da `null` olur. Durumlar: **0 `ok`**, **1 `too_few`**, **2 `unstable`**. Hata bitleri: **1 timeout**, **2 alt sınırın altında**, **4 üst sınırın üzerinde**, **8 tetikleme öncesi Echo HIGH**. Bitler birleştirilebilir. Kısmi hata içeren ama yeterli kararlı örneğe sahip pencere `ok` olabilir; hata maskesi korunur.

RF ayrıca donanımsal 16 bit CRC ve ACK kullanır. Uygulama CRC'si yanlış paket biçimini kontrol eder; kimlik doğrulaması veya şifreleme sağlamaz. ACK, bilgisayara kayıt yapıldığını göstermez. Yeniden denemede ACK kaybolmuş olsa da veri ulaşmış olabilir.

## Açılış ve mesaj kimliği

Uno'nun ilk 288 EEPROM baytı, 32 adet 9 baytlık açılış kaydı için ayrılmıştır. Kayıt; commit işareti, 32 bit sayaç ve sayacın bit tersinden oluşur. Son geçerli kayıttan yeni sayaç türetilir. Önce hedef slot geçersizleştirilir, commit en son yazılır. Yazılan değer doğrulanamazsa veri gönderimi durur.

Bu günlük yazmaları slotlara dağıtır; sınırsız EEPROM ömrü veya her güç arızasına karşı garanti sağlamaz. EEPROM silinirse, farklı kart aynı kutu kimliğini devralırsa veya tüm günlük bozulursa kimlikler eski verilerle çakışabilir. Böyle bir bakımda eski veriyi arşivleyip yeni veritabanı açın veya yeni kutu kimliği politikası belirleyin. Normal firmware yüklemesinden sonra da açılış kimliğinin arttığını gözleyin.

Bilgisayarda tekil anahtar `(node_id, boot_id, sequence)` olur. Aynı kimlik ve aynı ölçüm ikinci kayıt oluşturmaz. Aynı kimlikle farklı ölçüm 409 döndürür. Önceki açılıştan veya eski sıradan gelen paketler tarihçede tutulabilir ancak güncel durumu değiştirmez. Sayaç karşılaştırması 32 bit sarmayı destekler; karşılaştırılan sayaçlar arasında 2^31 veya daha fazla fark olmaması varsayılır.

## Gateway kuyrukları ve zaman

RF döngüsü SPI/radyo işlerini yürütür. USB çıktısı, LCD ve HTTP ayrı görevlerdir. Her çıkış kuyruğu 24 kayıttır. Dolu kuyrukta en eski kayıt bırakılır; düşürme sayacı artar. Ağ kapalıyken RF alımı sürer. LCD sonradan erişilemez olursa ekran güncellemeleri kapatılır; diğer işler sürer, yeniden etkinleştirmek için gateway yeniden başlatılır. HTTP kaydı gateway'e gelişinden itibaren 30 saniyeyi aşarsa gönderilmez. HTTP en fazla dört deneme yapar; 408/429 dışındaki 4xx hatalar yeniden denenmez. Güç kesilince RAM kuyrukları kaybolur.

`measured_uptime_ms` Uno saatidir; UTC değildir. `received_gateway_ms` ESP32 saatidir. `age_ms`, ilgili çıktı oluşturulurken gateway'de geçmiş süreyi içerir; USB köprüsü kendi kuyruk/bekleme süresini de ekler. Bilgisayar geliş zamanını UTC olarak kaydeder ve yaklaşık gözlem zamanını `geliş - age_ms` ile hesaplar. Radyo denemesi, ölçüm penceresi, USB sürücüsü ve ağ aktarım gecikmesinin tamamı bu yaşa dahil değildir. Cihaz saatleri senkronize değildir; bu alanlar kesin olay zamanı olarak kullanılmamalıdır.

## Bilgisayardaki doluluk ve durumlar

Her sensör için:

```text
doluluk = 100 × (boş_mesafe − ölçülen_mesafe) / (boş_mesafe − dolu_mesafe)
```

Geçersiz ölçümde hesap yapılmaz. Kutu boş mesafesinin varsayılan 50 mm toleranstan daha üzerinde ölçüm `outside_geometry` sayılır; büyük mesafe sıfıra sıkıştırılarak gizlenmez. Geçerli sonuçlar 0–100'e sınırlandırılır.

- Kalibrasyon doğrulanmamışsa `uncalibrated`, doluluk `null`.
- İki geçerli tahmin arasında 20 yüzde puanından fazla fark varsa `sensor_disagreement`, ortak doluluk `null`.
- Bir sensör geçerliyse `degraded`; tahmin tek sensörden gelir.
- İkisi de geçersizse `invalid`, doluluk `null`.
- Son kabul edilmiş değerden en az 25 yüzde puanlık değişimde üç ardışık uygun ölçüm beklenir. Adaylar ilk adayın ±8 yüzde puanında olmalıdır. Beklerken `change_pending`, güncel doluluk `null` olur; son geçerli değer ayrıca tutulur.
- Geçersiz pencere, sıra boşluğu, yeni açılış veya uzun veri arası aday sayacını sıfırlar. Kalıcı boşaltma da aynı doğrulamayla kabul edilir.
- 15 saniyeden eski veri `stale` olur; güncel doluluk `null` gösterilir. İlk gelişte zaten eski olan paket güncel durumu ilerletmez.

Bu kurallar malzemeyi tanımaz. İki sensörün aynı poşet/kartonu görmesi hâlinde yanlış ama uyumlu sonuç mümkündür. Ek sensör olmadan kapak açıklığı veya tam hacim kesin olarak belirlenemez.

## Teknik kaynaklar

- [RF24 API](https://rf24.readthedocs.io/en/latest/classRF24.html): kanal hesabı, plus olmayan modüllerde 250 kbps kısıtı, ACK ve FIFO.
- [RF24 hata açıklamaları](https://github.com/nRF24/RF24/blob/master/COMMON_ISSUES.md): ACK kaybı ve güç kararlılığı.
- [HC-SR04 teknik belgesi](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf): nominal mesafe aralığı ve tetikleme prensibi.
- [Espressif HTTPClient kaynağı](https://github.com/espressif/arduino-esp32/blob/master/libraries/HTTPClient/src/HTTPClient.cpp): bağlantı/okuma zaman aşımı ve POST arayüzü.
- [BTK teknik ölçütleri](https://www.btk.tr/s3/web-btk-site/7708c26c-5161-4919-8b3d-daa31d4ac8fb/2026/05/66efd802-05a1-4dc7-94a7-80b740125b49.pdf): frekans ve cihaz kullanım koşulları. Sahaya çıkışta güncel koşullar ayrıca doğrulanmalıdır.

