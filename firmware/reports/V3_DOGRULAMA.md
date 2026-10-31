# Firmware v3 doğrulaması — 31 Ekim 2026

## Tamamlanan kontroller

- Arduino Uno node 1: hedef derlemesi başarılı; RAM 387 / 2048 bayt,
  flash 7624 / 32256 bayt.
- ESP32 gateway: hedef derlemesi başarılı; RAM 47564 / 327680 bayt,
  uygulama flash 952573 / 1310720 bayt.
- 322 C++ çekirdek/LCD kontrolü, 61 gerçek Uno döngüsü kontrolü ve
  131 teslim/yanıt kontrolü başarılı.
- 35 firmware/kurulum Python testi ve 36 uygulama Python testi başarılı.
- Gerçek C++ v3 JSON çıktısı izole uygulama sunucusunda HTTP 201/200 ile
  kaydedildi; kabul yanıtı gerçek C++ ayrıştırıcıyla doğrulandı.
- Operasyon kilidi tutulurken telemetri POST, `/api/latest` ve `/health`
  istekleri başarılı: rota işlemleri donanım alımını bekletemiyor.
- PWA kabuk/projeksiyon kontrolü ve JavaScript sözdizimi kontrolü başarılı.

## Doğrulanan davranış

5 ölçüm çifti, her iki okuma arasında en az 450 ms sessizlik, yaklaşık 4,5 saniyelik
grup, geçerli çiftlerin aritmetik ortalaması, en az 3 geçerli çift. Hareket eden
geçerli mesafe grubu yayılım nedeniyle silinmiyor. Başlangıçta LCD `null mm`
yazmıyor; hatalı grubun ardından son iyi mesafe yaşıyla etiketleniyor. RF tekrarları
ölçüm zamanını yenilemiyor. LCD zamanı millis taşmasında doğru kalıyor.

HTTP/LCD posta kutuları bir kayıt tutuyor; yeni kayıt eski bekleyeni değiştiriyor.
10 saniyeden eski gönderim bırakılıyor. HTTP 4xx hatası yalnız o kaydı sonlandırıyor;
sunucu düzeldikten sonra yeni ölçüm için 60 saniyelik gereksiz kilit yok.

## Fiziksel doğrulama sınırı

Test sırasında seri port bulunmadı; kart yüklemesi, gerçek LCD, RF menzil ve fiziksel
sensör karşılaştırması yapılmadı. Yerel Wi-Fi doğrulaması örnek ayarlar buldu;
gerçek şifre bu çalışma sırasında girilmedi. Fiziksel doluluk kalibrasyonu operatörün
boş/dolu seviyelerinde ölçeceği ortalamalarla yapılmalı.

Güncel adımlar: [Yükleme ve bağlantı kılavuzu](../UPLOAD_AND_VERIFY.md).
