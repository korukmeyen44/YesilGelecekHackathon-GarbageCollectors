# Donanım yazılımı doğrulama raporu

Tarih: 30 Ekim 2026. Kapsam: v2 tek ortalama ve yaklaşık 10 saniyelik gruplar. Bu rapor yazılım kontrollerini fiziksel sensör/haberleşme testlerinden ayırır. Gerçek çöp kutusunda ölçülmüş doğruluk veya paket teslim oranı iddiası içermez.

## Yapılan yazılım kontrolleri

| Kontrol | Sonuç | Kapsam |
| --- | --- | --- |
| Ortak C++ çekirdeği | 459 kontrol geçti | Aritmetik ortalama, tek yuvarlama, geçersiz çiftler, sabit grup sayısı, rastgele bekleme sınırları, yayılım, CRC, 256 tek bit bozulması, v1 reddi, sayaç/zaman sarması |
| Gerçek Uno uygulaması ve taklit donanım katmanı | 101 kontrol geçti | 10'ar okuma, yaklaşık 10 saniye, ek 3 saniye beklemenin kaldırılması, timeout ile sabit grup, 6 çift eşiği, RF tekrarlarında aynı veri, millis sarması |
| Python ve yerel HTTP entegrasyonu | 27 test geçti | Tek ortalama kalibrasyonu, kısmi/geçersiz grup, v1/bozuk tanı verisi reddi, 35 saniye yaş eşiği, geçmiş kayıtlar, üç grup doğrulaması, HTTP/SQLite, seri satırlar |
| Üretim C++ JSON → bilgisayar alıcısı | Geçti | Gateway'in kullandığı JSON fonksiyonunun çıktısı Python doğrulamasına ve doluluk hesabına verildi |
| Komut satırı demo akışı | 13 kayıt geçti | Simülatör → alıcı → SQLite; boş, orta, kısmi/geçersiz/kararsız grup, dolu ve boşaltma |
| PowerShell derleme betiği | Sözdizimi kontrolü geçti | Betik ayrıştırması; kart yüklemesi yapılmadı |
| Metin ve değişiklik kontrolü | Geçti | UTF-8 kaynaklar, satır sonu boşlukları ve `git diff --check` |

Test komutu repo kökünden `python firmware/tools/run_tests.py` olarak tekrar çalıştırılabilir. Testler doğrudan firmware'in ortak C++ başlıklarını ve gerçek `src/node/main.cpp` dosyasını derler. Uno uygulaması testi yalnız GPIO/zaman/EEPROM/radyo donanım çağrılarını taklit eder; fiziksel cihaz testi değildir. Yerel HTTP testleri geçici port ve veritabanı kullanır. Simülasyon verileri fiziksel cihaz verisi değildir.

## Kart hedefleri için derleme

PlatformIO 6.1.18; AVR platformu 5.1.0; ESP32 platformu 6.9.0; RF24 1.4.11; LiquidCrystal_I2C 1.1.4 sabitlenmiştir.

| Hedef | Durum | Statik RAM | Flash |
| --- | --- | --- | --- |
| `uno_node_1` | Başarılı | 387 / 2048 bayt | 7630 / 32256 bayt |
| `uno_node_2` | Başarılı | 387 / 2048 bayt | 7630 / 32256 bayt |
| `uno_node_3` | Başarılı | 387 / 2048 bayt | 7632 / 32256 bayt |
| `esp32_gateway` | Doğrulanamadı: derleyici paketi indirilemedi | Ölçülmedi | Ölçülmedi |

RAM değerleri derleyicinin statik kullanım raporudur; çalışma anındaki stack/heap en yüksek kullanımını veya fiziksel kararlılığı kanıtlamaz. ESP32 için `espressif/toolchain-xtensa-esp32@8.4.0+2021r2-patch5` paketi için önceki denemelerde `Read timed out`, `NameResolutionError` ve `HTTPClientError` görüldü. V2 değişikliğinden sonra da kısa bağlantı zaman aşımıyla tekrar denendi; indirme tamamlanmadığı için deneme durduruldu. Zaman aşımı ve önbelleği atlayarak yeniden deneme uygulandı; paket edinilemedi. Bu nedenle ESP32 kaynak kodu mevcut olsa da gerçek ESP32 hedef derlemesi başarılı sayılmamıştır. Ağ erişimi düzeldiğinde `./firmware/tools/build.ps1 -Environment esp32_gateway` çalıştırılmalıdır.

## Yapılmayan fiziksel kontroller

Kartlara yazılım yüklenmedi. Sensör yüzeyi, kutu boyutu, gerçek kalibrasyon, NRF güç kararlılığı/menzili, LCD elektrik seviyeleri, Wi-Fi erişimi, E-Stop ve gerçek çöp malzemeleri bu ortamda ölçülmedi. USB seri köprüsünün satır işleme kodu otomatik test edildi; fiziksel COM bağlantısı denenmedi.

Gateway kuyruk taşması, Wi-Fi kesintisi altında radyo alımı, görevlerin çalışma zamanı bellek kullanımı ve LCD arızası gerçek ESP32 üzerinde ayrıca gözlenmelidir. Kaynak kodda görev ayrımı bulunması bu performansın sahada ölçüldüğü anlamına gelmez.

## Kalan saha adımları

1. Kimliklere göre üç Uno ve ESP32 yazılımını yükleyin.
2. Son çapraz montajda tek ortalamanın gerçek boş/dolu referanslarını v2 yerel kalibrasyona girin.
3. Önce USB, sonra Wi-Fi akışını doğrulayın.
4. `SAHA_TEST_PLANI.md` senaryolarını gerçek atıklarla doldurun.
5. Rota/heatmap tarafına yalnızca ölçüm kalitesi ve veri yaşıyla birlikte doluluk verisi verin.

