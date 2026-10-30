# YesilGelecekHackathon-GarbageCollectors

Arduino Uno, HC-SR04, NRF24 ve ESP32 tabanlı çöp kutusu ölçüm sistemi.

Donanım yazılımları, bilgisayar alıcısı, kurulum adımları ve test raporları için
[firmware klasörüne](firmware/README.md) bakın.

## Belediye operasyon paneli

Harita, açıklanabilir toplama öncelikleri, rota planlama, dolum tahmini, sensör
sağlığı ve senaryo bazlı etki hesabını içeren yerel MVP:

```powershell
python -m app.server
```

Tarayıcı: **http://127.0.0.1:8080**. Python 3.10+ yeterlidir; ek Python veya npm
paketi gerekmez. Panel 24 simülasyon kutusu ve veri bekleyen 1 canlı kutuyla açılır.
Donanımdan veri geldiğinde canlı kutular güncellenir.

[Kurulum, donanım bağlantısı ve demo akışı](app/README.md)
