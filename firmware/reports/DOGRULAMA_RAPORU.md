# Donanım yazılımı doğrulama raporu

Tarih: 30 Ekim 2026. Teslim: gc-v2-hardened-1. Hedef: bir Arduino Uno/node 1, ESP32 WROOM-32 gateway, Wi-Fi üzerinden uygulama backend'i; diğer 24 kutu mock. Bu rapor yazılım doğrulamasını fiziksel saha kabulünden ayırır.

## Yazılım doğrulaması

| Kontrol | Sonuç | Kapsam |
| --- | --- | --- |
| Ortak C++ çekirdeği | 459 kontrol geçti | Ortalama, hata maskeleri, CRC, bozuk paketler, sayaç/zaman sarması |
| Gerçek Uno kaynağı ve taklit donanım | 101 kontrol geçti | 10 çift ölçüm, zamanlama, kısmi/geçersiz grup, aynı kimlikle RF tekrarları |
| Gateway teslim politikası ve gerçek ArduinoJson parser | 131 kontrol geçti | Tekrar/sıra koruması, süre aşımı/sarması, backoff, yanlış endpoint, TLS CA koşulu, 200/201 kabulü ve kimlik eşleşmesi |
| Firmware Python/HTTP | 30 test geçti, atlanan yok | SQLite, kalibrasyon, kimlik, HTTP, gizli ayar üretimi, uygulamaya entegrasyon |
| Uygulama | 26 test geçti | Tek canlı / 24 mock ayrımı, rota, kapasite/süre, toplama, tahmin, kalıcılık |
| C++ JSON → gerçek uygulama HTTP → C++ kabul doğrulayıcısı | Geçti | Geçici test sunucusunda hem 201 yeni kayıt hem 200 tekrar kabulü; node 2 reddi, yabancı Origin reddi |

Toplam 691 C++ kontrolü ve 56 Python testi başarılıdır. Host testleri gerçek sensör/RF çağrılarını taklit eder. HTTP testi localhost'ta geçici veritabanıyla çalışır; fiziksel veri veya kablosuz teslim oranı kanıtı değildir.

Repo kökünden: `python firmware/tools/run_tests.py` ve `python -m unittest discover -s app/tests -v`. ArduinoJson önce ESP32 hedef derlemesiyle kurulur. Genel unittest keşfinde derlenmiş fixture testleri atlanabilir; tablodaki firmware sonucu run_tests.py ile elde edildi.

## Kart hedeflerine derleme

| Hedef | Sonuç | Statik RAM | Flash |
| --- | --- | --- | --- |
| uno_node_1 | Başarılı | 387 / 2048 bayt | 7722 / 32256 bayt |
| esp32_gateway | Başarılı | 47548 / 327680 bayt | 952077 / 1310720 bayt |

PlatformIO 6.1.18; AVR 5.1.0; ESP32 6.9.0 / Arduino ESP32 2.0.17; RF24 1.4.11; LCD 1.1.4; ArduinoJson 6.21.5 kullanıldı. Statik boyutlar heap/stack en yüksek tüketimini kanıtlamaz. Son build logu Git dışı `firmware/.build/final-build.log` dosyasındadır. Kart çıktıları `firmware/.pio/build/uno_node_1/firmware.hex` ve `firmware/.pio/build/esp32_gateway/firmware.bin` altında oluştu.

Önceki raporda ESP32 paketi indirilemediği için hedef doğrulanamıyordu. Bu çalışmada paketler indirildi. Windows uzun GCC include/komut yollarındaki `bits/c++config.h` ve `CreateProcess` hataları kısa paket yolu ve mevcut 8.3 adlarıyla giderildi. Çözüm build.ps1 içine alındı ve iki hedef başarıyla derlendi.

## Yapılan güçlendirmeler

- Uno: 8 saniyelik AVR watchdog ve reset kaydı. EEPROM açılış kimliği, sınırlı yankı beklemesi ve sabit örnek sayısı korundu.
- Gateway: ana döngü ve HTTP görevinde 12 saniyelik task watchdog. RF alımı HTTP/LCD işlemlerinden ayrı. Tek node 1 filtresi ve tekrar/eski RF paket koruması.
- Wi-Fi: tek yeniden bağlanma sahibi; 10–30 saniye ve küçük rastgele gecikme.
- HTTP: bağlantı/okuma zaman aşımı, en fazla 4 deneme, yönlendirme izlememe; 401/403/404 için 60 saniye bekleme. ArduinoJson ile 200/201 yanıtındaki kimlik ve yeni/tekrar bayrakları doğrulanır; uyuşmayan 2xx teslim sayılmaz.
- Kuyruk: 24 kayıt, en eskiyi bırakma, 30 saniye ömür. Eski veri güncel gösterilmez. Sayaçlar, son kabul yaşı ve heap minimumu loglanır.
- HTTPS: CA zorunlu, sertifika doğrulamasını atlayan yol yok; NTP zamanı. Bu yol derlendi; gerçek sertifikalı sunucuda denenmedi.
- Yükleme: şifre/anahtar komut satırında yer almaz. Git dışı yerel ayarlar, eşleşen backend başlatıcısı ve ESP32 yükleme öncesi ayar kontrolü eklendi.

## Fiziksel kabul ve üretim sınırları

Kartlara bu çalışma sırasında yükleme yapılmadı. Yalnız Bluetooth COM3/COM4 görüldü; Uno/ESP32 USB portu görünmedi. S24 FE ve 10.206.7.136 yerel şablona işlendi. Gerçek Wi-Fi şifresi henüz girilmedi. Yüklemeden önce configure_gateway.py çalıştırılıp şifre ve ortak anahtar girilerek yeniden derlenmeli. Yükleme betiği örnek şifreyle ESP32 yüklemesini engeller.

Sensör doğruluğu, NRF güç/menzil/parazit, LCD elektrik seviyeleri, E-Stop, fiziksel watchdog recovery, Wi-Fi kesintisi altında RF alımı ve uzun süreli bellek davranışı ölçülmedi. [Yükleme ve kabul kılavuzundaki](../UPLOAD_AND_VERIFY.md) adımlar gerçek kartlarda uygulanmalı.

Bu teslim yerel pilot için güçlendirilmiş, derlenmiş firmware'dir. RF kimlik doğrulaması/şifreleme, imzalı OTA, secure boot/flash encryption ve güç kesintisinde korunan çevrimdışı telemetri arşivi içermez. RAM kuyruğu yeniden başlatmada kaybolur; 30 saniyeden eski veri bilinçli atılır. Yerel HTTP şifreli değildir. Bu sınırlar kapanmadan ve saha kabulü yapılmadan genel belediye üretim sistemi olarak onaylanmış sayılmaz.
