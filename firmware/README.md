# Çöp kutusu ve istasyon firmware’ı — v3

**Akış:** Arduino Uno / iki HC-SR04 → NRF24 → ESP32 → Wi-Fi → uygulamanın
`POST /api/telemetry` adresi. Envanter: **1 fiziksel kutu (H1/node 1), 36 mock**.

Wi-Fi, backend, kalibrasyon ve iki karta ayrı yükleme için
[adım adım kılavuzu](UPLOAD_AND_VERIFY.md) izleyin. Backend için ayrıca collector
başlatmanız veya USB köprüsü çalıştırmanız gerekmez.

## Çöp kutusu: ne değişti?

- Sensörler sırayla tetiklenir. Her tamamlanan okumadan sonra **450 ms sessizlik**
  vardır; iki sensör aynı anda tetiklenmez. Bir sensör yaklaşık 0,9 saniyede bir okunur.
- Her grup sensör başına **5 okuma**, toplam **10 okuma / 5 çift** içerir.
  Ortalama yaklaşık **4,5–5 saniyede bir** RF ile gönderilir. Yankı ve RF yeniden
  denemeleri küçük ek gecikme yaratabilir; kesin zamanlı haberleşme iddiası yoktur.
- İki sensörün de geçerli olduğu çiftlerin aritmetik ortalaması alınır. En az
  **3 geçerli çift** gerekir. Tek sensör arızası sıfır mesafe veya sahte ortalamaya çevrilmez.
- Normal mesafe değişimi, yayılım 80 mm’yi aştı diye tüm ortalamayı artık silmez.
  Yayılım teşhis için JSON’da korunur. Medyan veya gizli aykırı değer elemesi yoktur.
- RF tekrarları aynı mesaj kimliğini ve aynı ortalamayı korur. Önceki grubun
  örnekleri yeni gruba karışmaz. Watchdog, açılış sayacı ve CRC/ACK korunur.

Ortalama = geçerli çiftlerdeki tüm mesafelerin toplamı / (2 × geçerli çift sayısı).
Eski **8/10**, 10 çiftin 8’inin geçerli olduğu anlamındaydı; pil göstergesi değildi.
Yeni firmware tanılamasında örneğin **4/5** görülebilir; LCD’de bu sayaç gösterilmez.

## İstasyon: LCD ve gönderim

| LCD | Anlam |
|---|---|
| `Olcum bekleniyor` | İlk grup henüz gelmedi; başlangıçta yaklaşık 5 saniye normal |
| `K1 Ort:220mm` | Gelen güncel grubun ortalaması |
| `Son 220mm 5s` + `Sensoru kontrol` | Yeni grup geçersiz; gösterilen değer 5 saniye önceki son geçerli ölçüm |
| `Son ...` + `RF veri bekliyor` | Kutudan uzun süredir yeni mesaj gelmiyor |
| `Olcum alinamadi` | Geçerli ortalama yok; sıfır veya `null mm` gösterilmez |
| `WiFi baglaniyor` | Ağ bağlantısı kuruluyor |
| `WiFi OK API OK` | Backend ölçümü kimliğiyle doğrulayıp kaydetti |
| `API ayari gerek` | Wi-Fi/API yerel ayarlarını hazırlayın |
| `API anahtar hata` / `API adres hata` | Kimlik veya endpoint ayarı hatalı |

LCD ve HTTP ayrı görevlerdir; ekran veya Wi-Fi beklemesi RF alımını durdurmaz.
HTTP için uzun geçmiş kuyruğu yerine **en yeni ölçüm** tutulur. Yeni ölçüm eski
yeniden denemeyi değiştirir; 10 saniyeden yaşlı gönderim bırakılır. Wi-Fi döndüğünde
eski birikim güncel veri gibi sırayla gönderilmez. USB JSON tanılama kuyruğu ayrıdır.

## Bağlantılar

| İşlev | Arduino Uno | ESP32 istasyon |
|---|---|---|
| Sensör 1 Trig / Echo | D2 / D3 | — |
| Sensör 2 Trig / Echo | D4 / D5 | — |
| NRF CE / CSN | D9 / D10 | GPIO4 / GPIO5 |
| NRF SCK / MISO / MOSI | D13 / D12 / D11 | GPIO18 / GPIO19 / GPIO23 |
| LCD SDA / SCL | — | GPIO21 / GPIO22 |

NRF beslemesi **3,3 V**, toprak ortak olmalı. LCD adresi varsayılan **0x27**.
5 V I2C pull-up seviyeleri ESP32 pinlerine doğrudan uygulanmamalı; devrenize göre
seviye dönüştürücü kullanın. HC-SR04 ölçüm aralığı firmware’de varsayılan 20–1200 mm;
üst sınır `include/common_config.h` üzerinden iki kart birlikte derlenerek değiştirilebilir.

## Protokol ve backend uyumu

RF sürümü **3**, paket **32 bayt**, kanal **76**, hız **1 Mbps**, CRC16 ve ACK.
**Uno ve ESP32 birlikte yüklenmeli.** Gateway eski v2 RF paketini kabul etmez.
Backend ise eski kayıtları/araçları bozmamak için v2 JSON (10 çift) ve yeni v3 JSON
(5 çift) kabul eder. Veritabanını silmeyin; gerçek ve mock depoları ayrı kalır.

Fiziksel doluluk yalnız ölçülmüş kalibrasyonla hesaplanır. Kalibrasyon yoksa ham
mesafe gelir, yüzde belirsiz kalır. Büyük doluluk değişimi backend’de üç ardışık
grupla doğrulanır: yeni ritimde yaklaşık **10–15 saniye** gerekebilir. LCD ham
ortalama gösterir; yüzde hesabı yapmaz. Güncellik sınırı varsayılan 35 saniyedir.

## Doğrulama

Repo kökünden:

```powershell
./firmware/tools/build.ps1 -Environment uno_node_1,esp32_gateway
python firmware/tools/run_tests.py
python -m unittest discover -s app/tests -q
```

Kodlar iki gerçek hedef için derlenir. Yerel testler gerçek Uno döngüsünü taklit
kart üzerinde çalıştırır; gerçek C++ JSON’u uygulamaya gönderip kaydedilen ölçümün
kabul yanıtını gerçek C++ ayrıştırıcıyla doğrular. Bunlar fiziksel menzil, güç
kararlılığı ve sensör doğruluğu testinin yerine geçmez.

Kaynak: [HC-SR04 veri sayfası, ölçümler arasında 60 ms üzeri bekleme önerisi](https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf).
`reports/` altındaki önceki v2 raporları tarihsel kayıttır; güncel ritim ve yükleme
adımları için bu belgeyi ve yükleme kılavuzunu kullanın.
