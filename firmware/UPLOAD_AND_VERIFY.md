# Tek gerçek kutu için yükleme ve doğrulama

Hedef akış: **Arduino Uno (node 1) → NRF24 → ESP32 WROOM-32 → S24 FE Wi-Fi → http://10.206.7.136:8080/api/telemetry**.
Panelde yalnız H1 canlıdır; diğer 24 kutu simülasyondur. Aşağıdaki bütün komutlar
repo ana klasöründeki PowerShell'de çalıştırılır.

## 1 Wi-Fi şifresini ve ortak API anahtarını hazırlayın

```powershell
python firmware/tools/configure_gateway.py --ssid "S24 FE" --backend-url "http://10.206.7.136:8080/api/telemetry"
```

Wi-Fi şifresi ekranda gösterilmeden sorulur; kaynak kod veya komut satırına
yazılmaz. Backend anahtarı için en az 16 karakter girin veya rastgele üretilmesi
için boş bırakın. Araç iki Git dışı yerel dosya hazırlar:

- `firmware/include/gateway_config.local.h`: ESP32'nin derlenecek Wi-Fi/API ayarları.
- `firmware/config/network.local.json`: backend ve bağlantı kontrolü için aynı API anahtarı;
  Wi-Fi şifresi bu JSON dosyasında tutulmaz. Panelin sorduğu anahtar `api_token` alanıdır.

Şifre ve anahtar yerel diskte/gateway firmware'inde bulunur; dosyaları paylaşmayın.
NVS/flash şifrelemesi veya güvenli önyükleme bu sürümde yapılandırılmadı.
Şifre henüz girilmediğinde hazır yerel başlık bilinçli olarak geçersiz örnek değer
taşır: USB derlemesi yapılabilir, ama Wi-Fi yükleme kontrolü geçmez.

```powershell
python firmware/tools/configure_gateway.py --check
```

Wi-Fi 2,4 GHz olmalı; giriş sayfası isteyen captive portal veya kurumsal 802.1X
akışı desteklenmez. Telefon erişim noktası cihazları birbirinden yalıtıyorsa
aynı ağa bağlı olmak tek başına yeterli değildir. Bilgisayarın IP'si değişirse
ayarları yeniden hazırlayıp ESP32'yi yeniden yükleyin.

## 2 Backend'i başlatın

```powershell
python firmware/tools/start_backend.py
```

Backend `0.0.0.0:8080` dinler ve gateway ile aynı anahtarı kullanır. Eski collector
veya başka backend aynı portta ayrıca açık olmamalı. Bu terminal açık kalsın.
Windows güvenlik duvarı sorarsa yalnız kullandığınız güvenilir yerel ağ için
Python'a erişim verin; güvenlik duvarını kapatmayın. Panel:
**http://10.206.7.136:8080**. Yerel ağ HTTP bağlantısı şifreli değildir.

Gerçek doluluk için `firmware/README.md` kalibrasyon adımlarını uygulayıp
`firmware/config/calibration.local.json` hazırlayın. Boş ve dolu kabul edilen
seviyeleri gerçek ortalama mesafeden ölçün; örnek 400/40 mm değerlerini fiziksel
ölçüm diye kullanmayın. Kalibrasyon yokken mesafe kaydedilir, doluluk `null` kalır.
Kalibrasyon dosyası değişirse backend yeniden başlatılmalı.

## 3 USB portlarını bulun

İki kartı USB'ye bağlayın; şarj kablosu yerine veri kablosu kullanın:

```powershell
./firmware/.tools/venv/Scripts/python.exe -m serial.tools.list_ports -v
```

Kartı çıkarıp yeniden takarak hangi portun hangi karta ait olduğunu belirleyin.
Bluetooth COM portlarını seçmeyin. Aşağıdaki COM5/COM6 yalnız örnektir.
Seri monitör yükleme sırasında portu tutmamalıdır.

## 4 Derleyin ve kartlara yükleyin

```powershell
./firmware/tools/build.ps1 -Environment uno_node_1,esp32_gateway
./firmware/tools/build.ps1 -Environment uno_node_1 -Upload -Port COM5
./firmware/tools/build.ps1 -Environment esp32_gateway -Upload -Port COM6
```

ESP32 yükleme öncesinde yerel ayarlar doğrulanır. Bazı ESP32 kartlarında
`Connecting...` sırasında BOOT tuşunu basılı tutup yazma başlayınca bırakmak
gerekebilir. Arduino Uno ve ESP32 hedeflerini birbirine karıştırmayın.
İlk kurulumda `build.ps1 -Setup` geliştirme araçlarını indirir. Windows GCC
yol/komut uzunluğu için paketler repo kökündeki Git dışı `.pio-packages` altında
ve mevcut 8.3 kısa yollarıyla kullanılır. 8.3 desteği olmayan çok uzun bir
checkout'ta projeyi daha kısa bir dizine taşımanız gerekebilir.

## 5 Gerçek akışı doğrulayın

```powershell
python firmware/tools/check_link.py --samples 3 --timeout 60
```

Bu araç sahte veri göndermez. Backend'de gerçek kaynaklı node 1 için üç farklı,
güncel mesaj kimliği gözler. Ham mesafeyi, kaliteyi ve doluluğu gösterir.
HTTP 201 yeni kayıt, 200 aynı ölçümün daha önce kaydedilmiş olmasıdır; gateway
yanıttaki `measurement_id` kimliklerini de eşleştirmeden teslimi başarılı saymaz.
Eski backend sürümüne karşı yeni gateway kullanmayın; ikisini birlikte güncelleyin.

Uno üzerindeki `rf_ack=yes` yalnız RF seviyesinde gateway'in paketi aldığını
gösterir. Backend'in kaydettiğini gösteren alan gateway'in `delivered` sayacıdır;
panelde güncel veri için ayrıca yukarıdaki bağlantı kontrolünü kullanın.

Gateway seri monitörü: 115200 baud. Ayarları açıkça seçerek monitor çalıştırmak için:

```powershell
$env:PLATFORMIO_CORE_DIR = "$PWD/firmware/.tools/platformio"
./firmware/.tools/venv/Scripts/python.exe -m platformio device monitor --port COM6 --baud 115200
```

| Gözlem | Anlam / yapılacak kontrol |
| --- | --- |
| `radio=error` | NRF kabloları, SPI, 3,3 V besleme ve ortak GND |
| `wifi=0` | SSID/şifre, 2,4 GHz ağ, sinyal veya erişim noktası |
| `wifi_ip=...`, `http=201/200`, artan `delivered` | Gateway backend'in kimliğe bağlı kabul yanıtını doğruluyor |
| `http=-102` | HTTP yanıtı ölçüme ait geçerli kabul kaydı değil; backend sürümü/adresi kontrol edilmeli |
| `http=401/403` | Anahtar uyuşmazlığı; otomatik gönderim 60 saniye bekler |
| `http=404` | Yanlış backend yolu; 60 saniye beklenir |
| `http=-1` veya diğer negatif kod | Backend kapalı, IP/port, ağ izolasyonu veya TLS bağlantısı |
| `http_expired` artıyor | Ölçümler 30 saniyelik gönderim ömrünü aştı; geçmiş ölçüm güncel diye gönderilmiyor |
| `uncalibrated` | Veri akıyor, ancak fiziksel kalibrasyon gerekli |
| `change_pending` | Büyük doluluk değişimi üç grup boyunca doğrulanıyor; yaklaşık 30 saniye sürebilir |

Ek USB köprüsü Wi-Fi akışı için gerekmez. Yalnız hata ayıklamak için açılabilir;
aynı ölçüm iki kanaldan giderse backend kimliğiyle tek kayıt tutar.

## Fiziksel kabul senaryoları

1. Boş, orta ve dolu hedeflerle mesafeyi karşılaştırın; iki sensör ortalaması
   çapraz akustik yol olduğundan dikey yükseklikle birebir aynı olmak zorunda değildir.
2. Bir sensörün yankısını engelleyin: geçersiz/kısmi kalite görünmeli; sıfır doluluk uydurulmamalı.
3. Wi-Fi'ı 60 saniye kapatın: Uno RF gönderimi devam etmeli; gateway kendi kendine
   yeniden bağlanmalı. Eski ölçümler güncel görünmemeli.
4. Backend'i durdurup yeniden açın: teslim sayacı tekrar artmalı; aynı kimlikli
   yeniden denemeler tek kayda dönüşmeli.
5. Uno ve gateway'i ayrı ayrı yeniden başlatın: yeni Uno boot kimliği kabul
   edilmeli; eski RF tekrarları son ölçümün zamanını yenilememeli.
6. En az bir saat açık tutun; gateway `heap_min`, teslim sayıları ve reset
   loglarını izleyin. Gerçek güç/menzil/bellek kararlılığı bu test yapılmadan onaylanmaz.

NRF modülleri **3,3 V** beslenmeli. Uno 5 V sensör devresi ile ESP32 3,3 V
GPIO'larını karıştırmayın; LCD I2C pull-up seviyeleri ESP32'ye uygun olmalı.
Pin eşleştirmeleri firmware README'de korunmuştur.

## Üretim sınırı

Bu teslim derlenmiş ve otomatik test edilmiş, yerel pilot için güçlendirilmiş
firmware'dir. Gerçek sahada doğrulanmış üretim sertifikası değildir. RF CRC/ACK
cihaz kimlik doğrulaması veya şifreleme sağlamaz. Kuyruk RAM'dedir; güç kesilince
kaybolur ve 30 saniyeden eski veri bilinçli olarak atılır. Kalıcı çevrimdışı arşiv,
imzalı OTA, secure boot/flash encryption, RF kimlik doğrulaması ve uzun süreli
elektriksel/çevresel saha testleri üretim dağıtımından önce ayrı tamamlanmalıdır.

HTTPS kullanımı için güvenilir CA zorunludur; `setInsecure` yoktur. Sistem zamanı
NTP ile alınır. TLS yolu derlendi, gerçek sertifikalı sunucuyla saha testi yapılmadı.
Yerel Python backend HTTPS sunmaz; internete açılacaksa sertifikalı ters proxy,
cihaz bazlı yetkilendirme ve üretim sunucusu gerekir.
