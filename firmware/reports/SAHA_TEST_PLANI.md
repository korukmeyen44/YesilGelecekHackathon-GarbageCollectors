# Gerçek çöp kutusunda doğrulama planı

Bu plan fiziksel doğrulama içindir. Aşağıdaki sonuç alanları henüz ölçülmemiştir. Yazılım testi geçmesi sensörün poşeti, eğimli kartonu veya gerçek çöp yüzeyini doğru ölçtüğünü kanıtlamaz.

## Deneme hazırlığı

Kutu boyutu ve iki sensörün konumu fotoğrafla kaydedilir. Sensörler kapaktan aşağı bakmalı; birbirine, duvara ve iç poşetin ağız kısmına yönelmemelidir. İlk deneme kuru, sabit ve geniş bir karton yüzeyle yapılır. NRF/LCD voltajları ve ortak toprak donanım sorumlusu tarafından kontrol edilir. Sensörleri poşet veya kumaşla kapatarak korumaya çalışmak akustik yolu değiştirebilir.

Her senaryoda en az 20 ölçüm çevrimi kaydedin. Düz hedefte referans uzaklık, iki sensörden ayrı ölçülür. Gerçek çöpte tek bir referans hacim iddiası yerine yüzey yerleşimi ve görünür engeller kaydedilir.

## Senaryolar

| Senaryo | İncelenecek davranış | Kabul yaklaşımı | Ölçülen sonuç |
| --- | --- | --- | --- |
| Boş kutu | Taban/poşet/duvar yankısı | Referans mesafelerle karşılaştırma, kararlı tekrar | Bekliyor |
| Düz karton, orta seviye | İki sensörün yaklaşık seviyesi | Her sensör için referans hata ve geçerli örnek oranı | Bekliyor |
| Düz karton, dolu seviye | Yakın sınır ve kalibrasyon | Dolu seviyesi kör bölge dışında; tutarlı değer | Bekliyor |
| Eğimli pizza kutusu/karton | Yankının başka yöne gitmesi | Geçersiz/kararsız okumalar görünür; boş kabul edilmez | Bekliyor |
| Buruşuk poşet | Değişken yankı | Ham yerleşim ve yayılım birlikte incelenir | Bekliyor |
| Kumaş/sünger | Yankı zayıflaması | Yetersiz örnekler doluluğa çevrilmez | Bekliyor |
| Dik şişe veya karton köşesi | Yerel yüksek engel | İki sensör farkı ve gerçek boş hacim raporlanır | Bekliyor |
| Bir tarafta yüksek yığın | Sensörler arası fark | Büyük yüzde farkında ortak doluluk üretilmez | Bekliyor |
| Ortada boşluk/çukur | Tabanın görülmesi | Yanlış düşük doluluk riski kaydedilir | Bekliyor |
| Sensöre sarkan iç poşet | Kararlı yanlış yakın mesafe | Yazılımın fark edemediği durum varsa açıkça kaydedilir; montaj düzeltilir | Bekliyor |
| Kapak açılması ve çöp atma | Geçici büyük değişim | Anlık değişim doğrulanmadan kalıcı yüzdeye dönüşmez | Bekliyor |
| Kutuyu boşaltma | Gerçek büyük azalma | Üç ardışık uyumlu ölçümden sonra yeni seviye kabul edilir | Bekliyor |
| Tek sensörün bağlantısını kesme | Kısmi ölçüm | `degraded` veya kararsız/hata; sonuca göre kaydedilir | Bekliyor |
| İki sensörde yankı yok | Bilinmeyen doluluk | `invalid`, güncel yüzde `null` | Bekliyor |
| Üç kutunun eşzamanlı çalışması | RF çarpışması/kayıp | Kimlikler karışmaz; sayaç aralıkları ve ACK hataları ölçülür | Bekliyor |
| Wi-Fi/API kapalı | RF ve kuyruk bağımsızlığı | USB ölçümleri sürer; kuyruk düşmeleri görünür | Bekliyor |
| Uno'yu yeniden başlatma | Açılış kimliği | Artan kimlik; eski mesajlar güncel durumu değiştirmez | Bekliyor |
| Gateway gücünü kesme/E-Stop | Kesinti ve yeniden başlama | RAM kaybı beklenir; arayüz veriyi eski gösterir | Bekliyor |

## Kaydedilecek değerler

- Tarih, kutu ve firmware sürümü, kanal/veri hızı, kalibrasyon kimliği.
- Yerleşim, atık malzemesi, yüzey açısı ve mümkünse fotoğraf.
- Her sensörün mesafesi, geçerli örnek sayısı, yayılımı, durum ve hata maskesi.
- Kutu/açılış/mesaj kimlikleri; RF ACK hata sayısı ve görülen sıra boşlukları.
- Bilgisayardaki doluluk, ölçüm kalitesi, veri yaşı ve değişim doğrulama süresi.
- Seri/HTTP kuyruk düşmeleri, HTTP hata/sona erme sayıları.

Düz hedef için ortalama mutlak hata ve en büyük hatayı referans ölçümlerden hesaplayın. Çöp yüzeyi için geçerli pencere oranını, uyuşmazlık sayısını ve yanlış kararlı ölçüm örneklerini raporlayın. Kabul edilebilir santimetre hatası gerçek kutu ve kullanım hedefiyle belirlenmelidir; bu teslim ölçülmemiş doğruluk yüzdesi içermez.

## Bilinen sınırlar ve müdahale

Eğimli sert yüzey yankıyı kaçırabilir; gözenekli atık yankıyı zayıflatabilir. Poşet kıvrımı, duvar ve köprü yapan karton kararlı yanlış sonuç oluşturabilir. Bunlar yalnızca filtreyle giderilemez. Sensör yerleşimi, iç poşetin sabitlenmesi, ek bakış noktası veya başka sensör türü gerekebilir.

Uzun süre HIGH kalan Echo hattı hata olarak raporlanır; sensör beslemesini ayrı anahtarlayan donanım olmadığı için otomatik güç döngüsü yapılmaz. Pil voltajını ölçen bağlantı belirtilmediğinden pil yüzdesi hesaplanmaz. Deep sleep uygulanmamıştır; birkaç saniyelik periyot demo içindir ve ölçülmüş saha pil ömrü anlamına gelmez. Gerçek kurulumda enerji tüketimi ve ölçüm periyodu ayrıca değerlendirilmelidir.

İlk saha turunda hata görülürse önce ham yerleşim ve örnekleri inceleyin. Yayılım eşiğini büyütmek, timeout'u boş kabul etmek veya sensör farkını zorla ortalamak sorunu gizler. Bu değişiklikleri bir sonraki testte ölçülmüş gerekçeyle değerlendirin.

