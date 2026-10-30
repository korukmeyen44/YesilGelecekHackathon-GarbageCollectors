# IoT Akıllı Atık Yönetim Sistemi: Donanım ve Haberleşme Spesifikasyonu (MVP)

Bu doküman, sistemin donanım mimarisini, pin eşleştirmelerini, güç katmanını, RF haberleşme protokolünü ve yazılım tarafında dikkat edilmesi gereken algoritmik detayları içermektedir. Yazılım geliştiricisi ve yapay zeka asistanları bu referansı temel alarak kod üretmelidir.

\---

## 1\. Sistem Mimarisi ve Veri Akışı

Sistem iki temel donanım katmanından oluşur:

```
\[ Çöp Kutusu Düğümü (Node) ]
  ├── 18650 Pil (3.7V) -> TP4056 -> Step-Up (5V)
  ├── 2x HC-SR04 Ultrasonik Mesafe Sensörü
  ├── NRF24L01 (2.4 GHz RF Verici)
  └── Arduino Uno (MCU)
            │
            │  (2.4 GHz RF - NRF24L01 / Kanal 108)
            ▼
\[ Yer İstasyonu (Gateway) ]
  ├── 18650 Pil (3.7V) -> TP4056 -> E-Stop Butonu -> HW-668 Boost (5V)
  ├── NRF24L01+PA+LNA (Harici Antenli Alıcı)
  ├── 16x2 I2C LCD Ekran (Mavi Arka Aydınlatmalı)
  ├── ESP32 WROOM-32 (MCU + Wi-Fi)
            │
            │  (Wi-Fi HTTP POST / REST API)
            ▼
\[ Backend / Merkezi Sunucu ]
```

\---

## 2\. Düğüm 1: Çöp Kutusu Devresi (Arduino Uno)

### 2.1. Güç Katı

* **Güç Kaynağı:** 1x 18650 3.7V Li-ion Pil.
* **Şarj \& Koruma:** Type-C TP4056 modülü.

  * Pil (+) $\\rightarrow$ `B+` | Pil (-) $\\rightarrow$ `B-`
  * Çıkış: TP4056 `OUT+` ve `OUT-` pinleri DC-DC Yükselticiye gider. (DW01A aşırı deşarj koruması aktif).
* **Voltaj Yükseltici:** DC-DC Step-Up modülü ile 5.0V regüle çıkış.

  * Step-Up 5V Çıkışı $\\rightarrow$ Arduino Uno `5V` pini.
  * Step-Up GND Çıkışı $\\rightarrow$ Arduino Uno `GND` pini.

### 2.2. Pin Eşleştirme Tablosu (Arduino Uno)

|Modül / Sensör|Modül Pini|Arduino Pini|Fonksiyon / Notlar|
|-|-|-|-|
|**Sensör 1 (HC-SR04)**|VCC|5V|5V Besleme Hattı|
||GND|GND|Ortak Şase|
||Trig|**D2**|Ultrasonik Darbe Çıkışı|
||Echo|**D3**|Yankı Süresi Girişi|
|**Sensör 2 (HC-SR04)**|VCC|5V|5V Besleme Hattı|
||GND|GND|Ortak Şase|
||Trig|**D4**|Ultrasonik Darbe Çıkışı|
||Echo|**D5**|Yankı Süresi Girişi|
|**NRF24L01 (Verici)**|VCC|**3.3V**|**ASLA 5V VERİLMEZ!**|
||GND|GND|Ortak Şase|
||CE|**D9**|Chip Enable|
||CSN|**D10**|SPI Chip Select|
||SCK|**D13**|Donanımsal SPI Clock|
||MOSI|**D11**|Donanımsal SPI MOSI|
||MISO|**D12**|Donanımsal SPI MISO|

\---

## 3\. Düğüm 2: Yer İstasyonu Devresi (ESP32 WROOM-32)

### 3.1. Güç \& E-Stop Katı

* **Güç Kaynağı:** 1x 18650 3.7V Li-ion Pil.
* **Şarj Modülü:** Type-C TP4056 (`OUT+` ve `OUT-`).
* **Acil Stop (Mantar) Butonu:**

  * TP4056 `OUT+` $\\rightarrow$ E-Stop Butonu **1** Nolu NC terminali.
  * E-Stop Butonu **2** Nolu NC terminali $\\rightarrow$ HW-668 Step-Up `VIN` pini.
  * *Mantık:* Buton basılı değilken sistem çalışır, butona basıldığında güç fiziksel olarak kesilir.
* **Step-Up Modülü (HW-668 / MT3608):**

  * Giriş gerilimini **tam 5.0V**'a regüle eder.
  * `OUT` $\\rightarrow$ ESP32 `VIN` ve I2C LCD `VCC` hattı.
  * `GND` $\\rightarrow$ ESP32 `GND` ve ortak toprak hattı.

### 3.2. Pin Eşleştirme Tablosu (ESP32)

|Modül|Modül Pini|ESP32 GPIO|Fonksiyon / Notlar|
|-|-|-|-|
|**NRF24L01+PA+LNA**|VCC|**3V3**|3.3V Besleme (Kondansatör destekli)|
||GND|GND|Ortak Şase|
||CE|**GPIO 4**|Chip Enable|
||CSN|**GPIO 5**|SPI Chip Select|
||SCK|**GPIO 18**|Donanımsal VSPI SCK|
||MISO|**GPIO 19**|Donanımsal VSPI MISO|
||MOSI|**GPIO 23**|Donanımsal VSPI MOSI|
|**16x2 I2C LCD Ekran**|VCC|**5V (VIN)**|3.3V bağlanırsa kontrast yetersiz kalır!|
||GND|GND|Ortak Şase|
||SDA|**GPIO 21**|Donanımsal I2C Data|
||SCL|**GPIO 22**|Donanımsal I2C Clock|

\---

## 4\. RF Haberleşme \& Veri Protokolü (NRF24L01)

### 4.1. Ortak RF Parametreleri

* **Frekans Kanalı:** `Channel 108` ($2400 + 108 = 2508\\text{ MHz}$). ESP32 Wi-Fi trafiğinin (2412–2462 MHz) sinyali bastırmasını engellemek için seçilmiştir.
* **Veri Hızı (Data Rate):** `RF24\_250KBPS` veya `RF24\_1MBPS` (250kbps menzil ve gürültü direnci için tercih edilir).
* **Güç Seviyesi (PA Level):**

  * Çöp Kutusu (Arduino): `RF24\_PA\_LOW` (Kondansatörsüz stabilite ve düşük tüketim için).
  * Yer İstasyonu (ESP32): `RF24\_PA\_HIGH` veya `RF24\_PA\_MAX`.
* **Adresleme (Pipe):** `const uint64\_t pipe = 0xE8E8F0F0E1LL;`

### 4.2. Ortak Payload Veri Yapısı (C++ Struct)

Her iki cihazda da birebir aynı bellek hizalamasına sahip struct kullanılmalıdır:

```cpp
struct CopKutusuVerisi {
  uint8\_t kutuID;       // Örn: 1, 2, 3
  uint8\_t dolulukOrani; // % cinsinden (0 - 100)
  uint16\_t mesafe1;     // cm cinsinden (Filtrelenmiş Sensör 1)
  uint16\_t mesafe2;     // cm cinsinden (Filtrelenmiş Sensör 2)
  uint32\_t mesajNo;     // Sıralı paket sayacı (Paket kaybı takibi için)
};
```

\---

## 5\. Yazılımcı İçin Algoritmik Kurallar ve Püf Noktaları

### 5.1. Ultrasonik Sensör Ölçümü ve Akustik Girişim (Crosstalk)

Sensörler karşılıklı baktığı için aynı anda tetiklenmemelidir:

1. Sensör 1 tetiklenir (`D2`), eko okunur (`D3`).
2. **Kritik:** En az **35 ms** beklenir (`delay(35);`). Bu süre odadaki/kovadaki artık ses yankısının sönümlenmesini sağlar.
3. Sensör 2 tetiklenir (`D4`), eko okunur (`D5`).

### 5.2. Hata Filtresi ve Doluluk Matematiği

HC-SR04 yumuşak yüzeylerden (poşet vb.) yankı alamadığında `0` veya aşırı yüksek değer döndürür.

* **Filtre:** Her sensörden ardışık 3 veya 5 ölçüm alınmalı; `0` olanlar elenmeli, kalan geçerli ölçümlerin aritmetik ortalaması veya medyanı alınmalıdır.
* **Doluluk Formülü:**
$$D\_{\\text{ölçülen}} = \\frac{D\_{\\text{sensör1}} + D\_{\\text{sensör2}}}{2}$$
$$\\text{Doluluk (%)} = \\left( \\frac{D\_{\\text{boş}} - D\_{\\text{ölçülen}}}{D\_{\\text{boş}}} \\right) \\times 100$$
*(Eğer $D\_{\\text{ölçülen}} \\ge D\_{\\text{boş}}$ ise Doluluk = %0; eğer $D\_{\\text{ölçülen}} \\le 0$ ise Doluluk = %100 sınırlandırılmalıdır).*

### 5.3. Gönderim Zamanlaması (Jitter)

Aynı ağda 3 çöp kutusu çalışırken paket çarpışmasını engellemek için Arduino döngüsüne asenkron gecikme eklenmelidir:

```cpp
delay(3000 + random(100, 1000)); // 3 saniye + rastgele varyasyon
```

### 5.4. LCD Gösterge Düzeni (ESP32)

16x2 LCD ekranın standart I2C adresi genelde `0x27` (bazı modellerde `0x3F`)'dir.

* **Satır 0:** `Kutu 1: %XX (YYcm)`
* **Satır 1:** `WiFi: OK | API: 200` (veya `Rx: Bekleniyor...`)

\---

## 6\. MVP Test Kod İskeletleri

### 6.1. Verici Kodu (Arduino Uno - Çöp Kutusu)

```cpp
#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

#define TRIG1\_PIN 2
#define ECHO1\_PIN 3
#define TRIG2\_PIN 4
#define ECHO2\_PIN 5

#define CE\_PIN   9
#define CSN\_PIN  10

RF24 radio(CE\_PIN, CSN\_PIN);
const uint64\_t pipe = 0xE8E8F0F0E1LL;

const int BOS\_MESAFE = 40; // Kovanın boş derinliği (cm) - Sahada güncellenecek

struct CopKutusuVerisi {
  uint8\_t kutuID;
  uint8\_t dolulukOrani;
  uint16\_t mesafe1;
  uint16\_t mesafe2;
  uint32\_t mesajNo;
} veri;

long mesafeOku(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long sure = pulseIn(echoPin, HIGH, 30000); // 30ms timeout (\~5 metre)
  if (sure == 0) return BOS\_MESAFE; // Yankı yoksa boş kabul et
  return sure \* 0.034 / 2;
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG1\_PIN, OUTPUT);
  pinMode(ECHO1\_PIN, INPUT);
  pinMode(TRIG2\_PIN, OUTPUT);
  pinMode(ECHO2\_PIN, INPUT);

  radio.begin();
  radio.setChannel(108);
  radio.setDataRate(RF24\_250KBPS);
  radio.setPALevel(RF24\_PA\_LOW);
  radio.openWritingPipe(pipe);
  radio.stopListening();

  veri.kutuID = 1;
  veri.mesajNo = 0;
}

void loop() {
  long d1 = mesafeOku(TRIG1\_PIN, ECHO1\_PIN);
  delay(40); // Crosstalk önleme gecikmesi
  long d2 = mesafeOku(TRIG2\_PIN, ECHO2\_PIN);

  float ortMesafe = (d1 + d2) / 2.0;
  if (ortMesafe > BOS\_MESAFE) ortMesafe = BOS\_MESAFE;
  if (ortMesafe < 0) ortMesafe = 0;

  int doluluk = ((BOS\_MESAFE - ortMesafe) / (float)BOS\_MESAFE) \* 100;
  if (doluluk < 0) doluluk = 0;
  if (doluluk > 100) doluluk = 100;

  veri.dolulukOrani = doluluk;
  veri.mesafe1 = d1;
  veri.mesafe2 = d2;
  veri.mesajNo++;

  bool basarili = radio.write(\&veri, sizeof(veri));
  Serial.print("Paket #"); Serial.print(veri.mesajNo);
  Serial.print(" | Doluluk: %"); Serial.print(veri.dolulukOrani);
  Serial.println(basarili ? " -> Iletildi" : " -> HATA");

  delay(2000 + random(100, 800)); // Rastgele gecikme
}
```

### 6.2. Alıcı Kodu (ESP32 - Yer İstasyonu + LCD)

```cpp
#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <Wire.h>
#include <LiquidCrystal\_I2C.h>

#define CE\_PIN  4
#define CSN\_PIN 5

RF24 radio(CE\_PIN, CSN\_PIN);
const uint64\_t pipe = 0xE8E8F0F0E1LL;
LiquidCrystal\_I2C lcd(0x27, 16, 2);

struct CopKutusuVerisi {
  uint8\_t kutuID;
  uint8\_t dolulukOrani;
  uint16\_t mesafe1;
  uint16\_t mesafe2;
  uint32\_t mesajNo;
} gelenVeri;

void setup() {
  Serial.begin(115200);

  // LCD Kurulumu
  Wire.begin(21, 22); // SDA, SCL
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Yer Istasyonu");
  lcd.setCursor(0, 1);
  lcd.print("Baslatiliyor...");

  // NRF Kurulumu
  radio.begin();
  radio.setChannel(108);
  radio.setDataRate(RF24\_250KBPS);
  radio.setPALevel(RF24\_PA\_HIGH);
  radio.openReadingPipe(1, pipe);
  radio.startListening();

  delay(1000);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Sinyal Bekleniyor");
}

void loop() {
  if (radio.available()) {
    radio.read(\&gelenVeri, sizeof(gelenVeri));

    Serial.printf("\[GELEN] Kutu: %d | Doluluk: %%%d | M1: %dcm | M2: %dcm | Pkt: %d\\n",
                  gelenVeri.kutuID, gelenVeri.dolulukOrani,
                  gelenVeri.mesafe1, gelenVeri.mesafe2, gelenVeri.mesajNo);

    // Ekrana Yazdır
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.printf("Kutu %d: %%%d Dolu", gelenVeri.kutuID, gelenVeri.dolulukOrani);
    lcd.setCursor(0, 1);
    lcd.printf("M:%dcm Pkt:#%d", (gelenVeri.mesafe1 + gelenVeri.mesafe2) / 2, gelenVeri.mesajNo);

    // TODO: Burada WiFiClient ve HTTPClient ile Backend'e POST atılacak.
  }
}
```

