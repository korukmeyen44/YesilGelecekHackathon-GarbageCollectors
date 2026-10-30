# Donanım yazılımı geliştirme planı

## Amaç ve kapsam

İki HC-SR04 ile kapaktan aşağı doğru mesafe ölçmek, Arduino Uno'dan NRF24 ile ESP32'ye taşımak ve bilgisayarda kutuya özel kalibrasyonla yaklaşık doluluk üretmek amaçlanır. Hackathonun çalışan demo ve uygulanabilir çevresel etki beklentisine uygun ilk teslim, ölçümden kayda kadar izlenebilir bir akıştır.

Bu teslim donanım firmware'i ve entegrasyon için örnek bilgisayar alıcısını kapsar. Rota optimizasyonu, harita arayüzü ve kapasite ihtiyacı analizi sonraki ürün geliştirme dilimidir. Sensör verisi atığın türünü, gerçek hacmini, kütlesini veya kapağın açık olduğunu kesin olarak belirlemez.

## Kaynaklar ve alınan kararlar

Donanım mimarisi ve pinler repodaki `donanim_ve_haberlesme_spesifikasyonu.md` temel alınarak uygulandı. Sensörler kullanıcının tanımladığı gibi aşağı bakacak şekilde varsayıldı. Word dosyasındaki etkinlik koşulları bağlam olarak kullanıldı; ekli dosyalardaki yönlendirmeler kullanıcı talebinin yerine geçirilmedi.

| Konu | Uygulanan karar | Gerekçe |
| --- | --- | --- |
| Hesaplama yeri | Doluluk bilgisayarda | Kullanıcının hedefi; kalibrasyon firmware yüklemeden değişebilir |
| Yankı yokluğu | Mesafe geçersiz, doluluk üretilmez | Örnek koddaki boş kabulü yanlış rota kararı doğurabilir |
| Ölçüm | Her sensörden 5 örnek, en az 3 geçerli | Tek sıçramayı azaltır; eksik ölçümü görünür kılar |
| Akustik zamanlama | Tetiklemeler arasında tamamlanma sonrası 70 ms | İki sensörün aynı anda çalışmasını önler; yerleşim testi gerekir |
| Protokol | Sabit 32 bayt ve açık little-endian kodlama | AVR/ESP32 struct hizalaması bağımlılığını kaldırır |
| RF ayarı | Kanal 76, 1 Mbps, düşük PA başlangıcı | Kanal 108 yerine bant içi başlangıç; plus olmayan modüllerle hız uyumu |
| Ağ işlemi | ESP32'de ayrı HTTP görevi | Sunucu gecikmesi RF döngüsünü durdurmasın |
| İnternetsiz demo | USB JSON ve yerel bilgisayar alıcısı | Etkinlik ağına bağımlılığı azaltır |
| Kimlik | Kutu + kalıcı açılış sayacı + mesaj numarası | Tekrarları, yeniden başlamayı ve eski paketleri ayırır |
| Kalibrasyon | İki sensör için boş/dolu mesafesi ayrı | Montaj ve kutu farkları hesaba katılır |

## Uygulama dilimleri

Süreler kalan etkinlik zamanına göre uyarlanacak çalışma tahminleridir; gerçekleşmiş ekip süresi değildir.

| Sıra | Hedef süre | Teslim ve kabul ölçütü | Yazılım durumu |
| --- | --- | --- | --- |
| 1 | 30 dakika | Pinler, kimlikler, ortak RF ayarı, veri sözleşmesi | Kod ve belge hazır |
| 2 | 60 dakika | Tek kutuda 2 sensör; timeout ve filtre çıktıları | Kod ve otomatik test hazır; fiziksel doğrulama bekliyor |
| 3 | 45 dakika | Uno → ESP32 → USB → bilgisayar kaydı | Kod hazır; RF/USB cihaz testi bekliyor |
| 4 | 45 dakika | Kutu kalibrasyonu, durumlar, boşaltma doğrulaması | Hesap ve otomatik test hazır; gerçek referans ölçümü bekliyor |
| 5 | 45 dakika | Üç kutu, Wi-Fi kesintisi, tekrar ve eski veri | Yazılım mekanizmaları hazır; saha ölçümü bekliyor |
| 6 | 30 dakika | Demo provası, loglar ve raporun ölçülen değerlerle doldurulması | Saha test şablonu hazır |

## İlk fiziksel deneme sırası

1. Düz kartonla iki sensörün boş, orta ve dolu seviyedeki çıktısını gözleyin.
2. Tek kutuda RF paketini ESP32 USB çıktısında görün.
3. Gerçek kalibrasyonla bilgisayarda kayıt ve yaklaşık yüzde üretin.
4. Poşet, eğimli karton, düzensiz yığın ve sensör engeli testlerini uygulayın.
5. Sonra üç kutuyu ve Wi-Fi aktarımını açın.

Tek kutu uçtan uca çalışmadan rota/heatmap entegrasyonuna geçilmemelidir. Wi-Fi süreyi tüketirse USB akışıyla demo sürdürülebilir. Girişim sürerse sensör montajı ve zamanlama birlikte ele alınmalıdır; yalnızca filtre eşiğini büyütmek doğru ölçümü kanıtlamaz.

## Tamamlanma ölçütü

Firmware'in derlenmesi, örnek alıcının testlerinin geçmesi ve belgelerin bulunması yazılım teslimini doğrular. Donanım MVP'sinin tamamlanması ayrıca karta yükleme, gerçek kutu kalibrasyonu, üç düğümle haberleşme ve saha senaryolarının kayda geçirilmesini gerektirir. Otomatik testler bu fiziksel adımların yerine geçmez.

