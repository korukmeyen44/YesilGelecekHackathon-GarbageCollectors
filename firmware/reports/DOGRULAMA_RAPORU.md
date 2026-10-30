# Donanım yazılımı doğrulama raporu

Tarih: 30 Ekim 2026. Bu rapor yazılım kontrollerini fiziksel sensör/haberleşme testlerinden ayırır. Gerçek çöp kutusunda ölçülmüş doğruluk veya paket teslim oranı iddiası içermez.

## Yapılan yazılım kontrolleri

| Kontrol | Sonuç | Kapsam |
| --- | --- | --- |
| Ortak C++ çekirdeği | 297 kontrol geçti | Medyan, yayılım, timeout, sınırlar, bilinen CRC vektörü, 256 tek bit bozulması, paket sözleşmesi, EEPROM slotu, sayaç/zaman sarması, JSON tamponu |
| Python ve yerel HTTP entegrasyonu | 26 test geçti | Kalibrasyon, bilinmeyen/tek sensörlü durum, uyuşmazlık, eski/tekrarlı paket, kimlik çakışması, üç çevrim doğrulama, SQLite yeniden açılışı, gerçek HTTP yanıtları, seri satır birleştirme |
| Üretim C++ JSON → bilgisayar alıcısı | Geçti | Gateway'in kullandığı JSON fonksiyonunun çıktısı Python doğrulamasına ve doluluk hesabına verildi |
| Komut satırı demo akışı | 13 kayıt geçti | Simülatör → alıcı → SQLite; boş, orta, hata, uyuşmazlık, dolu ve boşaltma |
| PowerShell derleme betiği | Sözdizimi kontrolü geçti | Betik ayrıştırması; kart yüklemesi yapılmadı |
| Metin ve değişiklik kontrolü | Geçti | UTF-8 kaynaklar, satır sonu boşlukları ve `git diff --check` |

Test komutu repo kökünden `python firmware/tools/run_tests.py` olarak tekrar çalıştırılabilir. Testler filtreyi/protokolü taklit eden ayrı bir uygulama yerine doğrudan firmware'in ortak C++ başlıklarını derler. Yerel HTTP testleri geçici port ve veritabanı kullanır. Simülasyon verileri fiziksel cihaz verisi değildir.

## Kart hedefleri için derleme

PlatformIO 6.1.18; AVR platformu 5.1.0; ESP32 platformu 6.9.0; RF24 1.4.11; LiquidCrystal_I2C 1.1.4 sabitlenmiştir.

| Hedef | Durum | Statik RAM | Flash |
| --- | --- | --- | --- |
| `uno_node_1` | Başarılı | 375 / 2048 bayt | 7484 / 32256 bayt |
| `uno_node_2` | Başarılı | 375 / 2048 bayt | 7484 / 32256 bayt |
| `uno_node_3` | Başarılı | 375 / 2048 bayt | 7486 / 32256 bayt |
| `esp32_gateway` | Doğrulanamadı: derleyici paketi indirilemedi | Ölçülmedi | Ölçülmedi |

RAM değerleri derleyicinin statik kullanım raporudur; çalışma anındaki stack/heap en yüksek kullanımını veya fiziksel kararlılığı kanıtlamaz. ESP32 için `espressif/toolchain-xtensa-esp32@8.4.0+2021r2-patch5` paketi indirilirken `Read timed out`, `NameResolutionError` ve son denemede `HTTPClientError` görüldü. Zaman aşımı ve önbelleği atlayarak yeniden deneme uygulandı; paket edinilemedi. Bu nedenle ESP32 kaynak kodu mevcut olsa da gerçek ESP32 hedef derlemesi başarılı sayılmamıştır. Ağ erişimi düzeldiğinde `./firmware/tools/build.ps1 -Environment esp32_gateway` çalıştırılmalıdır.

## Yapılmayan fiziksel kontroller

Kartlara yazılım yüklenmedi. Sensör yüzeyi, kutu boyutu, gerçek kalibrasyon, NRF güç kararlılığı/menzili, LCD elektrik seviyeleri, Wi-Fi erişimi, E-Stop ve gerçek çöp malzemeleri bu ortamda ölçülmedi. USB seri köprüsünün satır işleme kodu otomatik test edildi; fiziksel COM bağlantısı denenmedi.

Gateway kuyruk taşması, Wi-Fi kesintisi altında radyo alımı, görevlerin çalışma zamanı bellek kullanımı ve LCD arızası gerçek ESP32 üzerinde ayrıca gözlenmelidir. Kaynak kodda görev ayrımı bulunması bu performansın sahada ölçüldüğü anlamına gelmez.

## Kalan saha adımları

1. Kimliklere göre üç Uno ve ESP32 yazılımını yükleyin.
2. Gerçek boş/dolu mesafelerini her sensör için ölçüp yerel kalibrasyon dosyasına girin.
3. Önce USB, sonra Wi-Fi akışını doğrulayın.
4. `SAHA_TEST_PLANI.md` senaryolarını gerçek atıklarla doldurun.
5. Rota/heatmap tarafına yalnızca ölçüm kalitesi ve veri yaşıyla birlikte doluluk verisi verin.

