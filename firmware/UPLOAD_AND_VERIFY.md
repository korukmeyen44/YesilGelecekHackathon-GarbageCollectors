# v3 — iki karta yükleme ve uygulamaya bağlama

Komutları **repo ana klasöründe PowerShell** ile çalıştırın. Bir gerçek kutu ve
36 mock kullanılır. COM5/COM6 örnektir; kendi portlarınızla değiştirin.

## 1. Aynı Wi-Fi ve bilgisayar IP’si

Bilgisayar ve ESP32 aynı **2,4 GHz** Wi-Fi’da olmalı. S24 FE erişim noktasını
2,4 GHz / uyumlu WPA2 modunda kullanın. Bilgisayarın IPv4 adresini kontrol edin:

```powershell
ipconfig
```

Önceki IP’niz **10.206.7.136**. Değiştiyse aşağıdaki URL’de yenisini yazın.
ESP32 için `localhost` bilgisayar değildir.

## 2. Wi-Fi ayarları

```powershell
python firmware/tools/configure_gateway.py --ssid "S24 FE" --backend-url "http://10.206.7.136:8080/api/telemetry"
```

Şifre gizli olarak sorulur. Backend anahtarında boş Enter, ortak rastgele anahtar
üretir. İki Git dışı dosya hazırlanır:

- `firmware/include/gateway_config.local.h`: ESP32 Wi-Fi şifresi ve API ayarları.
- `firmware/config/network.local.json`: aynı API adresi/anahtarı; Wi-Fi şifresi içermez.

Bu dosyalar paylaşılmamalı. Wi-Fi/IP değişince komutu yeniden çalıştırın, backend’i
yeniden başlatın ve **ESP32’yi tekrar yükleyin**. Uno’nun Wi-Fi ayarı yoktur.

```powershell
python firmware/tools/configure_gateway.py --check
```

## 3. Portlar ve ayrı yüklemeler

Araçlar ilk kez kurulacaksa:

```powershell
./firmware/tools/build.ps1 -Setup
```

USB veri kablolarıyla bağlayın; yükleme sırasında seri monitörleri kapatın:

```powershell
./firmware/.tools/venv/Scripts/python.exe -m serial.tools.list_ports -v
```

**Çöp kutusu — Arduino Uno, node 1:**

```powershell
./firmware/tools/build.ps1 -Environment uno_node_1 -Upload -Port COM5
```

**İstasyon — ESP32:**

```powershell
./firmware/tools/build.ps1 -Environment esp32_gateway -Upload -Port COM6
```

İkisini de v3’e yükleyin. ESP32’de `Connecting...` takılırsa BOOT tuşunu yazma
başlayana kadar basılı tutmanız gerekebilir. Gerçek portu tahmin etmeyin; kartı
çıkarıp takarak port listesinden ayırt edin. Yükleme komutları derlemeyi de yapar.

## 4. Backend’i ağa açın

Eski backend/collector aynı portta açıksa Ctrl+C ile kapatın. Yeni terminalde:

```powershell
python firmware/tools/start_backend.py
```

Bu komut **0.0.0.0:8080** üzerinden gerçek uygulamayı başlatır, ortak anahtarı
yerel dosyadan alır. Böylece ESP32’den erişilebilir; ayrıca collector veya USB
köprüsü açmayın. Panel: **http://10.206.7.136:8080**.

Panel anahtar sorarsa `network.local.json` içindeki `api_token` değerini kullanın.
Windows güvenlik duvarı erişim sorarsa kullandığınız güvenilir ağ için Python’a
izin verin. Erişim noktası istemci yalıtımı da cihazlar arası bağlantıyı engelleyebilir.
ESP32 bağlantısı yerel HTTP’dir; telefondaki PWA/GPS için HTTPS kurulumu ayrı konudur.

Ham mesafe akışını başka terminalden kontrol edin:

```powershell
python firmware/tools/check_link.py --samples 3 --timeout 45
```

Bu araç **sahte RF verisi göndermez**. Üç farklı, güncel ve geçerli v3 ortalaması
görmeden PASS vermez. Kalibrasyon yoksa ham mesafe kontrolü geçebilir, yüzde henüz yoktur.

## 5. Fiziksel doluluk kalibrasyonu

Boş kutuda LCD’deki birkaç `Ort` değerini gözleyin. Sonra dolu kabul ettiğiniz
seviyede aynı ortalamayı ölçün. İkisini **mm** olarak şu araca girin:

```powershell
python firmware/tools/calibrate_bin.py --node 1
```

Araç boş/dolu değerlerini sorar, `calibration.local.json` oluşturur; mevcut yerel
dosya varsa `.bak` yedeğini alır. `boş > dolu >= 20` olmalı. Örnek 400/40 mm
değerlerini gerçek ölçüm diye kullanmayın. Firmware varsayılan sınırı 1200 mm.

Backend’i Ctrl+C ile kapatıp yeniden başlatın:

```powershell
python firmware/tools/start_backend.py
```

Doluluk dahil kontrol:

```powershell
python firmware/tools/check_link.py --samples 3 --timeout 45 --require-fill
```

Haritada **H1 / Canlı sensör** güncellenir. Mock kutular fiziksel ölçümle değişmez.
Paneli yenileyin; kurulu PWA’da güncelleme uyarısı varsa `Yenile` seçin.
Büyük yüzde değişimi onaylanırken `change_pending` ve geçici belirsizlik normaldir;
üç ardışık grupla yaklaşık 10–15 saniyede doğrulanır.

## LCD ve temel arıza ayrımı

- İlk açılışta `Olcum bekleniyor`; yaklaşık 5 saniyede ilk ortalama.
- `K1 Ort:220mm`: güncel ortalama. Eski 8/10 sayacı artık ekranda yok.
- `Son 220mm 5s` / `Sensoru kontrol`: yeni grup alınamadı; önceki değer etiketli.
- `RF veri bekliyor`: kutu beslemesi, NRF kabloları ve 3,3 V besleme kontrolü.
- `WiFi baglaniyor`: SSID/şifre, 2,4 GHz ve erişim noktası kontrolü.
- `Sunucu kontrol`: backend, IP/port, aynı ağ ve güvenlik duvarı kontrolü.
- `API anahtar hata`: gateway/backend anahtarı uyuşmuyor; yapılandırmayı yenileyin.
- `WiFi OK API OK`: backend ölçümü kaydetti; yalnız RF ACK’inden farklıdır.

Teknik hata kodları ve geçerli çift sayıları 115200 baud USB JSON/loglarında
korunur. LCD’de ASCII kullanılması karakter bozulmasını önler.

Gerçek kabul denemesi: boş/orta/dolu hedef, bir sensörü engelleme, Wi-Fi kapatıp
açma, backend yeniden başlatma ve iki kartı ayrı yeniden başlatma. Haberleşmenin
kendi kendine toparlandığını ve eski ölçümün güncel diye gösterilmediğini gözleyin.
Fiziksel saha doğruluğu ve kararlılığı bu testler yapılmadan garanti edilemez.
