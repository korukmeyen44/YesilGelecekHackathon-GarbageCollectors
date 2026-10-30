# Çöp kutusu donanım yazılımları

Bu klasör iki HC-SR04 bağlı Arduino Uno düğümünü, NRF24 üzerinden veri alan ESP32 WROOM-32 yer istasyonunu ve bilgisayarda çalışan örnek alıcıyı içerir. Amaç, ölçüm hatalarını saklamadan mesafe toplamak ve kalibrasyona göre yaklaşık doluluk üretmektir. Gerçek hacim, atık türü ve kapak durumu doğrudan ölçülmez.

## Klasörler

| Yol | İçerik |
| --- | --- |
| `src/node/main.cpp` | Arduino sensör ölçümü, kalıcı açılış sayacı ve RF gönderimi |
| `src/gateway/main.cpp` | ESP32 RF alımı; ayrı görevlerde LCD, USB JSON ve HTTP gönderimi |
| `include/` | Ortak ayarlar, ölçüm filtresi, 32 bayt protokol ve JSON üretimi |
| `config/` | Bilgisayarda kullanılan kalibrasyon dosyaları |
| `tools/collector.py` | Yerel HTTP alıcı, SQLite kayıtları ve doluluk hesabı |
| `tools/serial_bridge.py` | Wi-Fi yerine USB üzerinden bilgisayara aktarım |
| `tools/simulate.py` | Donanımdan bağımsız, açıkça simülasyon etiketli örnek veriler |
| `tests/` | Üretim C++ kodunu ve bilgisayar alıcısını sınayan testler |
| `reports/` | Plan, protokol, riskler, saha testi ve doğrulama raporu |

## Başlangıç kararları

- Doluluk Arduino'da hesaplanmaz. İki sensörün filtrelenmiş mesafeleri ve hata durumları bilgisayara ulaşır.
- Varsayılan RF kanalı **76**, veri hızı **1 Mbps**, payload **32 bayt**, CRC **16 bit**, otomatik ACK açıktır. Bu, ilk dosyadaki kanal 108 ve platforma bağlı struct aktarımının yerine geçer. Seçilen kanal sahada girişim testinden geçirilmelidir; bant içinde olmak tek başına tüm telsiz koşullarını sağladığını göstermez.
- İlk yüklemede **USB JSON açıktır, HTTP kapalıdır**. Wi-Fi şifresi gerekmeden uçtan uca deneme yapılabilir.
- Örnek fiziksel kalibrasyon `calibrated=false` içerir. Gerçek ölçüler girilmeden doluluk `null`, durum `uncalibrated` olur.
- Kart üzerindeki LCD mesafe ve bağlantı durumunu gösterir; bilgisayardaki kalibrasyon ve zamansal doğrulamayı tekrarlamaz.

## Derleme ve karta yükleme

Komutları repo kökünde PowerShell ile çalıştırın. Python 3 ve ilk kurulumda internet gerekir. Araçlar bu klasördeki, Git'e alınmayan `.tools` içine kurulur.

```powershell
./firmware/tools/build.ps1 -Setup
```

Bu komut varsayılan olarak ilk Uno ve ESP32 yazılımlarını derler. Üç Uno için:

```powershell
./firmware/tools/build.ps1 -Environment uno_node_1,uno_node_2,uno_node_3,esp32_gateway
```

Portları kendi cihazlarınıza göre değiştirin. Karta yükleme cihazdaki mevcut programın yerini alır. Aynı RF ağında her Uno'ya farklı kimlik yükleyin.

```powershell
./firmware/tools/build.ps1 -Environment uno_node_1 -Upload -Port COM3
./firmware/tools/build.ps1 -Environment esp32_gateway -Upload -Port COM5
```

Uno bağlantıları: sensörler Trig/Echo **D2/D3**, **D4/D5**; NRF CE/CSN **D9/D10**, SPI **D13/D11/D12**. ESP32: NRF CE/CSN **4/5**, SCK/MISO/MOSI **18/19/23**; LCD SDA/SCL **21/22**. Bunlar paylaşılan donanım dosyasıyla aynıdır.

NRF beslemesi 3,3 V olmalıdır. PA+LNA güç kararlılığı donanımda doğrulanmalıdır. 5 V LCD kartının SDA/SCL pull-up seviyelerinin ESP32 GPIO'larına uygunluğu kontrol edilmelidir; gerekiyorsa seviye dönüştürücü kullanılmalıdır. Bu elektriksel sorunlar firmware ile giderilemez.

## Önce donanımsız doğrulama

Bir terminalde yerel alıcıyı başlatın. Simülasyon için ayrı veritabanı kullanın; fiziksel ölçümlerle karıştırmayın.

```powershell
python firmware/tools/collector.py --config firmware/config/calibration.demo.json --db firmware/.build/demo.sqlite3
```

Diğer terminalde:

```powershell
python firmware/tools/simulate.py
Invoke-RestMethod http://127.0.0.1:8080/api/latest
```

Senaryo boş kutu, artan seviye, tek/çift sensör hatası, sensör uyuşmazlığı ve boşaltmayı gösterir. Veriler `source=simulator` taşır. Simülatörü aynı saniyede tekrar başlatmayın; açılış kimliği saniyelik zamandan üretilir. Gerçek donanım doğruluğunu kanıtlamaz.

## Gerçek kutuyu kalibre etme

```powershell
Copy-Item firmware/config/calibration.example.json firmware/config/calibration.local.json
```

1. Kapak kapalıyken her sensörün boş kutuya mesafesini milimetre olarak ölçün; `empty_mm` alanlarına yazın.
2. Kutunun dolu kabul edileceği seviyeyi belirleyin. Sensörün yakın ölçüm sınırının üzerinde kalacak `full_mm` değerlerini ayrı ayrı yazın.
3. Kutunun duvarı, sarkan iç poşet ve sabit çıkıntılardan yankı alınmadığını farklı yüksekliklerde düz kartonla kontrol edin.
4. İlgili kutu için `calibrated=true` yapın; `calibration_id` değerini ölçümünüzü tanımlayan yeni bir değerle değiştirin.
5. Alıcıyı yeniden başlatın. Dosya çalışma sırasında otomatik yeniden yüklenmez. Eski kayıtlar eski kalibrasyon kimliğini korur.

`empty_mm > full_mm >= 20` olmalıdır. Varsayılan düğüm üst ölçüm sınırı 1200 mm'dir. Daha uzun kutuda `include/common_config.h` ayarını değiştirip hem Uno hem gateway'i yeniden derleyin. Bilgisayardaki kalibrasyonu değiştirmek tek başına düğümün ölçüm aralığını değiştirmez.

## USB ile gerçek ölçüm alma

Kalibrasyon sonrası bir terminalde:

```powershell
python firmware/tools/collector.py --config firmware/config/calibration.local.json --db firmware/.build/hardware.sqlite3
```

Diğer terminalde, ESP32'nin portunu seçerek:

```powershell
./firmware/.tools/venv/Scripts/python.exe firmware/tools/serial_bridge.py --port COM5
```

Seri monitör portu aynı anda açık olmamalıdır. Bağlantı hızı **115200**. USB portunu açmak ESP32'yi yeniden başlatabilir. Köprü USB okumayı ayrı iş parçacığında sürdürür; ağ isteği okumayı durdurmaz. Kuyruk en fazla 24 ölçüm tutar; dolunca en eski kayıt düşürülür ve terminale yazılır. Başarısız gönderimde en fazla üç deneme yapılır. Köprü yeniden başlatılırsa RAM kuyruğu kaybolur.

## Wi-Fi ve HTTP aktarımı

```powershell
Copy-Item firmware/include/gateway_config.example.h firmware/include/gateway_config.local.h
```

Yerel dosyada 2,4 GHz Wi-Fi bilgilerini, bilgisayarın yerel IP adresiyle API URL'sini ve gerekiyorsa token'ı girin. Dosya Git dışında tutulur. `localhost`/`127.0.0.1` ESP32 açısından bilgisayarınızı ifade etmez.

Bilgisayarda alıcıyı yerel ağa açın:

```powershell
$env:GC_API_TOKEN = 'choose-an-ascii-demo-token'
python firmware/tools/collector.py --host 0.0.0.0 --config firmware/config/calibration.local.json --db firmware/.build/hardware.sqlite3
```

Aynı token'ı gateway yerel ayarına yazın ve ESP32'yi yeniden derleyip yükleyin. Windows güvenlik duvarı ve erişim noktasının istemci yalıtımı bağlantıyı etkileyebilir. Wi-Fi HTTP ile USB köprüsü aynı anda gönderirse alıcı aynı ölçümü tek kayıt olarak tutar.

Bu örnek yerel hackathon ağı içindir. HTTP şifreli değildir; Wi-Fi ve RF kimlik doğrulaması üretim sistemi seviyesinde değildir. İnternete açık kurulum, TLS, cihaz kimliği doğrulaması ve kalıcı gateway kuyruğu bu MVP'nin kapsamı dışındadır.

## Arayüze sunulan sonuç

- `POST /api/telemetry`: yeni kayıt **201**, aynı ölçüm **200**, aynı kimlikle farklı veri **409**.
- `GET /api/latest`: ölçümü alınmış kutuların son durumu. Token ayarlıysa GET istekleri de Bearer token ister.
- `GET /health`: yerel alıcının yanıt verebildiğini gösterir; sensörlerin sağlıklı olduğunu garanti etmez.
- `fill_percent`: güncel ve kabul edilmiş yaklaşık doluluk; belirsizlikte/eski veride `null`.
- `sensors`: iki sensörün mesafesi, yayılımı, geçerli örnek sayısı ve hata bilgisi; kalibrasyon öncesinde de görülebilir.
- `measurement_quality`: `ok`, `degraded`, `invalid`, `sensor_disagreement`, `change_pending`, `uncalibrated` veya `calibration_changed`.
- `freshness`: `fresh`/`stale`; `last_valid_fill_percent` ile önceki değer ve `last_valid_age_ms` ayrıca sunulur.

Arayüz `null` değerini sıfıra çevirmemelidir. `degraded` tek sensörlü tahmini ifade eder. Rota kararında bu tahminin kullanılıp kullanılmayacağı uygulama politikasıdır. Geçersiz veya eski verili kutu otomatik olarak boş kabul edilmemelidir.

## Testleri çalıştırma

Python 3 ve erişilebilir bir `g++` gerekir:

```powershell
python firmware/tools/run_tests.py
```

Komut doğrudan firmware'in kullandığı filtre/protokol/JSON kodunu derler; C++ çıktısını gerçek yerel HTTP/SQLite testleriyle birlikte doğrular. Sonuçlar ve fiziksel test sınırları için [doğrulama raporunu](reports/DOGRULAMA_RAPORU.md), saha denemesi için [test planını](reports/SAHA_TEST_PLANI.md) okuyun.

