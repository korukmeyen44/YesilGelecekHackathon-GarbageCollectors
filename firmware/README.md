# Çöp kutusu donanım yazılımları

Bu klasör iki HC-SR04 bağlı Arduino Uno düğümünü, NRF24 üzerinden veri alan ESP32 WROOM-32 yer istasyonunu ve bilgisayarda çalışan örnek alıcıyı içerir. Amaç, ölçüm hatalarını saklamadan mesafe toplamak ve kalibrasyona göre yaklaşık doluluk üretmektir. Gerçek hacim, atık türü ve kapak durumu doğrudan ölçülmez.

**Güncel teslim:** Tek gerçek kutu (node 1), S24 FE Wi-Fi ağı ve
`http://10.206.7.136:8080/api/telemetry` için
[yükleme ve gerçek bağlantı doğrulama kılavuzunu](UPLOAD_AND_VERIFY.md) izleyin.
Yerel Wi-Fi şifresi ve ortak API anahtarı `configure_gateway.py` ile hazırlanır;
gateway yükleme betiği eksik/uyuşmayan ayarlarla ESP32'ye yüklemeyi durdurur.
ArduinoJson 6.21.5 ile backend kabul yanıtı ölçüm kimliğine bağlanır; yalnız
200/201 durumu yeterli değildir. Backend ve gateway birlikte güncellenmelidir.

## Klasörler

| Yol | İçerik |
| --- | --- |
| `src/node/main.cpp` | Arduino sensör ölçümü, kalıcı açılış sayacı ve RF gönderimi |
| `src/gateway/main.cpp` | ESP32 RF alımı; ayrı görevlerde LCD, USB JSON ve HTTP gönderimi |
| `include/` | Ortak ayarlar, çift sensör ortalaması, 32 bayt v2 protokol ve JSON üretimi |
| `config/` | Bilgisayarda kullanılan kalibrasyon dosyaları |
| `tools/collector.py` | Yerel HTTP alıcı, SQLite kayıtları ve doluluk hesabı |
| `tools/serial_bridge.py` | Wi-Fi yerine USB üzerinden bilgisayara aktarım |
| `tools/simulate.py` | Donanımdan bağımsız, açıkça simülasyon etiketli örnek veriler |
| `tests/` | Üretim C++ kodunu ve bilgisayar alıcısını sınayan testler |
| `reports/` | Plan, protokol, riskler, saha testi ve doğrulama raporu |

## Başlangıç kararları

- Doluluk Arduino'da hesaplanmaz. İki sensörün firmware üzerinde hesaplanan tek ortalama mesafesi ve grup hata bilgileri bilgisayara ulaşır.
- Varsayılan RF kanalı **76**, veri hızı **1 Mbps**, payload **32 bayt**, CRC **16 bit**, otomatik ACK açıktır. Bu, ilk dosyadaki kanal 108 ve platforma bağlı struct aktarımının yerine geçer. Seçilen kanal sahada girişim testinden geçirilmelidir; bant içinde olmak tek başına tüm telsiz koşullarını sağladığını göstermez.
- İlk yüklemede **USB JSON açıktır, HTTP kapalıdır**. Wi-Fi şifresi gerekmeden uçtan uca deneme yapılabilir.
- Örnek fiziksel kalibrasyon `calibrated=false` içerir. Gerçek ölçüler girilmeden doluluk `null`, durum `uncalibrated` olur.
- Kart üzerindeki LCD tek ortalama mesafeyi, geçerli çift sayısını ve bağlantı durumunu gösterir; bilgisayardaki kalibrasyon ve zamansal doğrulamayı tekrarlamaz.

## Yaklaşık on saniyelik ortalama

Her grup **10 çift ölçümden**, yani sensör başına 10 ve toplam 20 okumadan oluşur. Sensörler sırayla çalışır. İlk okuma öncesinde ve sonraki her okuma öncesinde **425–575 ms** rastgele beklenir. Yalnız beklemelerin beklenen toplamı **10.000 ms**, teorik aralığı **8.500–11.500 ms** olur. Yankı okuması, döngü ve RF yeniden denemeleri nedeniyle rapor aralığı kesin 10 saniye değildir. Eski üç saniyelik ek çevrim beklemesi kaldırıldı.

Bir çiftte iki okuma da geçerliyse ikisi ortalamaya katılır. Geçersiz çift sıfır veya tek sensör değeriyle doldurulmaz. Grup 10 denemede biter; hata olduğunda sınırsız yeni örnek toplanmaz. En az **6 geçerli çift** gerekir. Aritmetik ortalama, geçerli çiftlerin iki mesafesinin toplamının `2 × geçerli_çift_sayısı` değerine bölünmesiyle hesaplanır; yuvarlama en son yapılır. Medyan kullanılmaz.

İki sensörün birbirinden farklı mesafeleri ortalamaya katılır. Sensörler arasındaki fark artık birleştirmeyi engellemez. Grup içindeki çift ortalamalarının en büyüğü ile en küçüğü arasında 80 mm'den fazla fark varsa grup `unstable` sayılır ve kabul edilmiş mesafe `null` olur. Bu eşik başlangıç ayarıdır; sahada doğrulanmalıdır.

**Protokol sürümü 2:** Ayrı sensör mesafeleri yerine tek `measurement` nesnesi gönderilir. Kutu/açılış/mesaj kimlikleri korunur. `measurement` içinde ortalama mesafe, yayılım, 10 deneme sayısı, geçerli çift sayısı, sensör başına geçerli örnek sayıları/hata maskeleri ve gerçek grup süresi bulunur. RF paket boyu yine 32 bayttır; bu değişiklik paket boyunda tasarruf iddiası taşımaz.

Uno, ESP32 ve bilgisayar alıcısını birlikte v2'ye güncelleyin. Eski v1 paketleri kabul edilmez. Eski sensör başına kalibrasyon dosyası yerine aşağıdaki tek ortalama kalibrasyonu gerekir. Önceki kayıtları arşivlemek için yeni bir veritabanı kullanabilirsiniz; yeni kalibrasyon kimliği eski güncel yüzdeyi geçersiz kılar.

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

Senaryo boş kutu, artan seviye, eksik/geçersiz çiftler, kararsız ölçüm grubu ve boşaltmayı gösterir. Veriler `source=simulator` taşır. Simülatörü aynı saniyede tekrar başlatmayın; açılış kimliği saniyelik zamandan üretilir. Gerçek donanım doğruluğunu kanıtlamaz.

## Gerçek kutuyu kalibre etme

Eski yerel dosyanız varsa önce yedekleyin. Ardından v2 örneğini kopyalayın:

```powershell
Copy-Item firmware/config/calibration.example.json firmware/config/calibration.local.json
```

1. İki sensörü planladığınız çapraz konumda sabitleyin. Kapak kapalıyken boş kutuda birkaç grubun tek ortalama çıktısını gözleyin. Bu referansı ilgili kutunun `measurement.empty_mm` alanına yazın.
2. Dolu kabul edilen seviyede aynı işlemi yapıp `measurement.full_mm` değerini belirleyin. Ham mesafeler çapraz akustik yolları temsil ettiği için kutunun dikey yüksekliğini doğrudan girmek yerine gerçek ortalama çıktısını kalibre edin.
3. Sarkan poşet, duvar ve sabit çıkıntılardan yanlış yankı gelmediğini farklı seviyelerde düz hedefle kontrol edin. Çapraz montaj tek başına bütün yanlış yankıları ortadan kaldırmaz.
4. İlgili kutu için `calibrated=true` yapın ve `calibration_id` değerini ölçümünüzü tanımlayan yeni bir değerle değiştirin.
5. Alıcıyı yeniden başlatın. Dosya çalışma sırasında otomatik yeniden yüklenmez. Geçmiş kayıtlar kendi kalibrasyon kimliğini korur.

`empty_mm > full_mm >= 20` olmalıdır. Varsayılan düğüm üst ölçüm sınırı 1200 mm'dir. Daha uzun akustik yol gerekiyorsa `include/common_config.h` ayarını değiştirip hem Uno hem gateway'i yeniden derleyin. Bilgisayardaki kalibrasyonu değiştirmek tek başına sensör ölçüm sınırını değiştirmez.

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

Bu örnek yerel hackathon ağı içindir. HTTP şifreli değildir; RF cihaz kimlik
doğrulaması/şifrelemesi yoktur. Gateway HTTPS istemcisinde güvenilir CA ve NTP
zamanı zorunludur; Python backend için HTTPS ters proxy ayrıca gerekir. TLS
istemcisi derlendi, gerçek sertifikalı sunucuda denenmedi. Kalıcı gateway kuyruğu,
RF kimlik doğrulaması, secure boot ve imzalı OTA bu teslimde yoktur.

## Arayüze sunulan sonuç

- `POST /api/telemetry`: yeni kayıt **201**, aynı ölçüm **200**, aynı kimlikle farklı veri **409**.
- `GET /api/latest`: ölçümü alınmış kutuların son durumu. Token ayarlıysa GET istekleri de Bearer token ister.
- `GET /health`: yerel alıcının yanıt verebildiğini gösterir; sensörlerin sağlıklı olduğunu garanti etmez.
- `fill_percent`: güncel ve kabul edilmiş yaklaşık doluluk; belirsizlikte/eski veride `null`.
- `measurement`: tek ortalama mesafe, çift ortalamalarının yayılımı, geçerli çift sayısı, sensör başına örnek sayıları/hata maskeleri ve `window_duration_ms`; kalibrasyon öncesinde de görülebilir. Ayrı sensör mesafeleri yoktur.
- `measurement_quality`: `ok`, `degraded`, `invalid`, `outside_geometry`, `change_pending`, `uncalibrated` veya `calibration_changed`.
- `freshness`: `fresh`/`stale`; `last_valid_fill_percent` ile önceki değer ve `last_valid_age_ms` ayrıca sunulur.

Arayüz `null` değerini sıfıra çevirmemelidir. `degraded`, 10 çiftin en az 6 tanesinin geçerli olduğu kısmi grubu ifade eder; tek sensörlü tahmin değildir. Rota kararında bu tahminin kullanılıp kullanılmayacağı uygulama politikasıdır. Geçersiz veya eski verili kutu otomatik olarak boş kabul edilmemelidir. Veri 35 saniye sonra `stale` olur. Büyük doluluk değişiklikleri üç ardışık grup ile doğrulandığından yaklaşık 30 saniyelik bir doğrulama süreci oluşabilir; her 10 saniyelik paket anında kabul edilmiş yeni yüzde anlamına gelmez.

## Testleri çalıştırma

Python 3 ve erişilebilir bir `g++` gerekir. Önce ESP32 hedefini derleyerek
sabitlenmiş ArduinoJson başlıklarını indirin:

```powershell
./firmware/tools/build.ps1 -Environment esp32_gateway
python firmware/tools/run_tests.py
```

Komut doğrudan firmware'in kullandığı ortalama/protokol/JSON kodunu ve taklit donanım katmanıyla gerçek Uno uygulamasını derler; C++ çıktısını gerçek yerel HTTP/SQLite testleriyle birlikte doğrular. Sonuçlar ve fiziksel test sınırları için [doğrulama raporunu](reports/DOGRULAMA_RAPORU.md), saha denemesi için [test planını](reports/SAHA_TEST_PLANI.md) okuyun.

