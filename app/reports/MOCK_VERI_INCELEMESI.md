# Mock veri inceleme sonucu

Mevcut veri temel operasyon demosu için yeterli örnekler içerir. İleri zaman serisi değerlendirmesi ve anlamlı bölgesel yoğunluk senaryoları için kapsam kısmen yeterlidir; üretici güçlendirilmelidir. Bu çalışma veri üreticisini veya veritabanını değiştirmedi.

- 24 simülasyon kutusu, 14 günlük geçmiş, 32280 kayıt.
- 8 temel hız: 0.7, 1.1, 1.8, 2.0, 2.6, 3.2, 4.5, 8.0 yüzde puan/saat. Her hızdan üç kutu.
- En hızlı / en yavaş oranı: 11.43.
- Kalite alanı: {"ok": 32280}. Tahmini eksik örnek yuvası: 0.
- Mevcut durumlar: {"normal": 21, "offline": 1, "unstable": 1, "degraded": 1}. Bu bayraklar geçmişteki kesintilerin kanıtı değildir.
- 294 toplama kaydı, 270 gözlenen büyük düşüş; 16 ilave kayıt aynı düşüş aralığıyla eşleşiyor, 8 kayıtta >20 puan düşüş doğrulanmıyor.
- Veri özeti SHA-256: `f0ffe9944d2d0ded1717ba5190f3cd3dd576147202e124d2fb933d2f39471ef5`.

## Senaryo yeterliliği

Harita, doluluk eşiği, orta seviyede hızlı dolum, yavaş dolum, elle arıza demosu ve rota adayları için örnekler var. Güncel seviye ile günlük birikim farklı büyüklüklerdir. Toplama, seviyesi düşen bir bölgenin atık üretiminin azaldığı anlamına gelmez.

Zaman serisi için ortak gündüz/gece katsayısı ve küçük rastgele değişim var. Hafta sonu/etkinlik/tatil profili yok. Son dolum dönemi hedef son seviyeye doğrusal bağlanıyor; bazı kutularda birkaç günlük geçmiş bu nedenle düzleşiyor. Üretici hızı modele girdi yapılırsa sonuç yapay biçimde kolaylaşır. 14 gün yalnız iki haftalık tekrar içerir; gerçek genelleme kanıtı değildir.

Koordinatlar heatmap için teknik girdi sağlar. Bölgesel sıcak/soğuk alan üretmek üzere açık bir mekânsal süreç yok. 3 komşunun ortalama hızıyla temel hız korelasyonu -0.327; bu yalnız betimleyici bir kontroldür, anlamlılık testi değildir. Gelecekte heatmap'te nokta sayısı, doluluk yükü ve birikim hızı ayrı tanımlanmalı; KDE ağırlığı ve yarıçapı belirtilmelidir.

## Jüri için seçilen yöntem

`mock-veri-inceleme.html` tek dosyalı, internet gerektirmeyen grafik raporudur. Tanımlı hız çubukları, aynı 72 saatte hızlı/orta/yavaş kutular, kutu × gün ısı matrisi, koordinat dağılım grafiği, karar örnekleri ve sınırlamalar birlikte gösterilir. `mock-veri-ozeti.png` sunuma eklenebilecek görseldir; `mock-veri-inceleme.json` hesaplanan sayısal dökümdür. Rapor kaynak verinin o andaki kopyasına bağlıdır; demo ilerledikçe yeniden üretilmelidir.

## Sonraki veri üreticisi önerisi

8–12 haftalık sürümlü/seed'li geçmiş; bölge ve zaman bağımlı profiller; hafta sonu ve ani yük; gerçek dolum sürecinden ayrı sensör gürültüsü/arıza kayıtları; tekil toplama olayları; eğitim-test ayrımı ve basit tahminlerle karşılaştırma önerilir. Bu bir geliştirme önerisidir, uygulanmış özellik değildir. Sentetik başarıdan gerçek saha başarısı çıkarılamaz.

## Kutular

| Kutu | Tanımlı hız (yp/saat) | Gözlenen ortanca (yp/saat) | Şimdiki durum |
| --- | --- | --- | --- |
| S01 | 2.0 | 2.33 | normal |
| S02 | 1.1 | 1.3 | normal |
| S03 | 8.0 | 9.49 | normal |
| S04 | 3.2 | 3.75 | normal |
| S05 | 0.7 | 0.83 | normal |
| S06 | 4.5 | 5.33 | normal |
| S07 | 1.8 | 2.11 | normal |
| S08 | 2.6 | 3.0 | normal |
| S09 | 2.0 | 2.35 | normal |
| S10 | 1.1 | 1.3 | normal |
| S11 | 8.0 | 9.39 | normal |
| S12 | 3.2 | 3.79 | normal |
| S13 | 0.7 | 0.8 | normal |
| S14 | 4.5 | 5.33 | normal |
| S15 | 1.8 | 2.08 | normal |
| S16 | 2.6 | 3.04 | normal |
| S17 | 2.0 | 2.35 | normal |
| S18 | 1.1 | 1.28 | normal |
| S19 | 8.0 | 9.54 | normal |
| S20 | 3.2 | 3.73 | normal |
| S21 | 0.7 | 0.84 | normal |
| S22 | 4.5 | 5.27 | offline |
| S23 | 1.8 | 2.1 | unstable |
| S24 | 2.6 | 3.07 | degraded |

Yöntem kaynakları: [Zaman serisi doğrulaması](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation), [QGIS KDE ağırlık ve yarıçap tanımı](https://docs.qgis.org/3.40/en/docs/user_manual/processing_algs/qgis/interpolation.html#heatmap-kernel-density-estimation).
