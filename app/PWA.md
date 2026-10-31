# GC Sürücü — telefon ve PWA

## Kullanım

1. Uygulamayı telefonda **güvenilir bir HTTPS adresinden** açın.
2. Üstteki indirme simgesine dokunun. Android kurulum penceresini kullanır;
   iPhone'da Safari → Paylaş → Ana Ekrana Ekle yolunu izleyin.
3. Haritada Simülasyon veya Canlı sensör kaynağını seçin. Ortadaki kamyon
   butonunun altında hangi kaynakla sefer oluşturulacağı yazılıdır.
4. Kamyon butonuna dokunun. Yol üzerinden yeni sefer hazırlanır, tam ekran
   şoför görünümü açılır ve GPS izni istenir. İzin verilmezse rota önizlemesi
   kullanılabilir; yapay konumla canlı sürüş taklidi yapılmaz.

Canlı kutuda yeterli veri yoksa otomatik durak üretilmez. Tek araçlı, süreyi
azaltan mevcut rota yöntemi kullanılır; canlı trafik veya küresel optimum
garantisi yoktur. Yol çizgisi alınamazsa sürüş başlatılmaz. Demo sürüşü ayrı,
açıkça simülasyon olarak etiketlenmiş bir seçenektir.

## HTTPS

Bilgisayarda `http://127.0.0.1:8080` geliştirme için güvenli bağlam sayılır.
Telefondaki `http://10.206.7.136:8080` ise güvenli bağlam **değildir**: servis
çalışanı ve canlı GPS kullanılamaz. Bu tarayıcı kısıtı PWA koduyla aşılamaz.

Güvenilir alan adınıza ait sertifika varsa uygulama HTTPS ile başlatılabilir:

```powershell
python -m app.server --host 0.0.0.0 --port 8443 --tls-cert C:\certs\fullchain.pem --tls-key C:\certs\privkey.pem
```

Sertifikadaki alan adıyla açın; telefonda sertifika uyarısı olmamalı.
Alternatif olarak mevcut HTTP backend'in önüne güvenilir HTTPS sağlayan ters
vekil koyun. ESP32'nin mevcut yerel HTTP bağlantısı korunacaksa bu ikinci
yöntemle yerel 8080 hizmetini açık bırakın. Bu değişiklik otomatik olarak alan
adı, sertifika, dış erişim veya firmware adresi oluşturmaz.

## Çevrimdışı davranış

- İlk başarılı açılışta uygulama kabuğu, simgeler ve yerel kampüs geometrisi
  hazırlanır. Bölgesel bina geometrisi kullanıldığında önbelleğe alınır.
- Anahtarsız yerel kullanımda son pano ve plan cihazda saklanır. Yetkilendirme
  anahtarı ve anahtarla alınan API yanıtları kalıcı olarak saklanmaz.
- Bağlantı kesilirse kayıtlı görünümün tarihi ve **Çevrimdışı** uyarısı çıkar.
  Canlı ölçümler güncel kabul edilmez. Yeni rota ve kayıt işlemleri kapalıdır.
- Kayıtlı yol rotası ve cihaz GPS'i ile önizleme/takip kullanılabilir. Yeni
  yönlendirme hesabı, uydu ve yol harita karoları için bağlantı gerekir.
  Harita çevrimdışında yerel şehir görünümüne geçer; tüm şehir için çevrimdışı
  navigasyon paketi indirilmez.
- Bir işlem çevrimdışında kuyruğa atılıp sonradan gizlice gönderilmez.
- Güncelleme hazır olduğunda kullanıcıya sunulur. Aktif sürüşte yenileme
  engellenir; kendiliğinden sayfa yenilemesi yapılmaz.
- GPS foreground kullanım içindir. Ekran kilidi/arka plan sürekli konum
  garantisi yoktur. Sayfa gizlenince takip durur; geri dönünce GPS başlat ile
  devam edilir. Desteklenen cihazda aktif GPS sırasında ekran açık tutulur.

## Arayüz

Açık/koyu tema üstteki güneş/ay düğmesinden değiştirilir ve cihazda hatırlanır.
Harita ışığı ayrı bir ayardır: saate göre / gündüz / gece. Saate göre modu
Trabzon'un tarih ve konumuna göre yaklaşık güneş yüksekliği kullanır.

Zaman merceği 0–24 saat aralığında mevcut tahmin modelinin eğimini kullanır.
Tahmini işaretler kesik kenarlıdır; yeterli geçmiş yoksa belirsiz görünür.
Bu görünüm gerçek ölçüm, simülasyon saati veya planlama girdisini değiştirmez.
Rota planlama ve hızlı sürüş güncel ölçümlere döner.

## Kontrol

```powershell
python -m unittest discover -s app/tests -q
node app/tests/test_map_scene.cjs
node app/tests/test_route_math.cjs
node app/tests/test_future_pwa.cjs
```

Yeni sürümde `web/sw.js` içindeki kabuk sürümünü artırın. Masaüstü tarayıcı
kontrolleri fiziksel telefonda kurulum ve gerçek GPS saha testinin yerine geçmez.
