#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <esp_task_wdt.h>
#include <LiquidCrystal_I2C.h>
#include <esp_system.h>
#include <atomic>
#include "gateway_config.h"
#include "radio_setup.h"
#include "telemetry_json.h"
#include "http_receipt.h"
#include "lcd_status.h"

namespace {
constexpr uint8_t kQueueDepth = 24;
struct Record { gc::Packet packet; uint32_t receivedMs; };
RF24 radio(4, 5);
LiquidCrystal_I2C lcd(GC_LCD_ADDRESS, 16, 2);
QueueHandle_t serialQueue = nullptr;
QueueHandle_t httpQueue = nullptr;
QueueHandle_t lcdQueue = nullptr;
std::atomic<uint32_t> serialDropped(0), httpDropped(0), rejected(0), httpExpired(0), httpFailed(0);
std::atomic<uint32_t> lcdDropped(0);
std::atomic<uint32_t> delivered(0), duplicateRf(0), lastDeliveryMs(0), httpSuperseded(0);
std::atomic<int> httpStatus(0);
std::atomic<bool> wifiConnected(false);
uint32_t gatewayBootId = 0;
std::atomic<bool> radioReady(false), lcdReady(false), httpEnabled(false);
bool gatewayReady = false;
gc::DisplayState displayStates[gc::kMaxNodeId];
uint32_t nextRadioCheckMs = 0;
uint8_t displayNode = 0;
gc::ReplayGuard replayGuard;

bool serialize(const Record& record, char* body, size_t capacity) {
    gc::GatewayMetadata metadata;
    metadata.gatewayId = GC_GATEWAY_ID;
    metadata.gatewayBootId = gatewayBootId;
    metadata.receivedMs = record.receivedMs;
    metadata.ageMs = millis() - record.receivedMs;
    metadata.httpDropped = httpDropped.load();
    metadata.serialDropped = serialDropped.load();
    metadata.rejected = rejected.load();
    return gc::toJson(record.packet, metadata, body, capacity);
}

void enqueueLatest(QueueHandle_t queue, const Record& record, std::atomic<uint32_t>& dropped) {
    if (xQueueSend(queue, &record, 0) == pdTRUE) return;
    Record old;
    if (xQueueReceive(queue, &old, 0) == pdTRUE) ++dropped;
    if (xQueueSend(queue, &record, 0) != pdTRUE) ++dropped;
}

void serialWorker(void*) {
    uint32_t lastStatsMs = millis();
    Record record;
    char body[1024];
    for (;;) {
        if (xQueueReceive(serialQueue, &record, pdMS_TO_TICKS(100)) == pdTRUE) {
            if (serialize(record, body, sizeof(body))) Serial.println(body);
            else ++serialDropped;
        }
        if (millis() - lastStatsMs >= 10000) {
            Serial.printf("# stats rf_rejected=%lu serial_dropped=%lu http_dropped=%lu http_expired=%lu http_failed=%lu wifi=%u http=%d lcd=%u lcd_dropped=%lu delivered=%lu rf_duplicate=%lu ack_age_ms=%lu heap_free=%lu heap_min=%lu\n",
                static_cast<unsigned long>(rejected.load()), static_cast<unsigned long>(serialDropped.load()),
                static_cast<unsigned long>(httpDropped.load()), static_cast<unsigned long>(httpExpired.load()),
                static_cast<unsigned long>(httpFailed.load()), wifiConnected.load(), httpStatus.load(),
                lcdReady.load(), static_cast<unsigned long>(lcdDropped.load()),
                static_cast<unsigned long>(delivered.load()), static_cast<unsigned long>(duplicateRf.load()),
                static_cast<unsigned long>(delivered.load() ? millis()-lastDeliveryMs.load() : 0),
                static_cast<unsigned long>(ESP.getFreeHeap()), static_cast<unsigned long>(ESP.getMinFreeHeap()));
            if (wifiConnected.load()) Serial.printf("# wifi_ip=%s\n", WiFi.localIP().toString().c_str());
            Serial.printf("# latest_only superseded=%lu report_pairs=%u\n",static_cast<unsigned long>(httpSuperseded.load()),gc::kMeasurementPairs);
            lastStatsMs = millis();
        }
    }
}

void httpWorker(void*) {
    esp_task_wdt_add(nullptr);
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(false); // One explicit reconnect owner, bounded backoff.
    WiFi.begin(GC_WIFI_SSID, GC_WIFI_PASSWORD);
    const bool tls = strncmp(GC_API_URL, "https://", 8) == 0;
    if (tls) configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
    uint32_t nextConnectMs = millis() + 10000;
    uint8_t connectFailures = 0;
    Record record;
    bool pending = false;
    uint8_t attempts = 0;
    uint32_t nextAttemptMs = 0;
    char body[1024];
    for (;;) {
        esp_task_wdt_reset();
        const uint32_t now = millis();
        const bool connected = WiFi.status() == WL_CONNECTED;
        wifiConnected.store(connected);
        if (connected) {
            connectFailures = 0;
            nextConnectMs = now + 10000;
        } else if (gc::due(now, nextConnectMs)) {
            WiFi.disconnect(false, false);
            WiFi.begin(GC_WIFI_SSID, GC_WIFI_PASSWORD);
            nextConnectMs = now + gc::reconnectDelay(connectFailures, esp_random() % 501);
            if (connectFailures < 5) ++connectFailures;
        }
        Record newest;
        if (xQueueReceive(httpQueue, &newest, 0) == pdTRUE) {
            if (pending) ++httpSuperseded;
            record = newest; // Replace an old retry with the latest RF sample.
            pending = true;
            attempts = 0;
            nextAttemptMs = now;
        }
        if (pending && gc::expired(now, record.receivedMs)) {
            ++httpExpired;
            pending = false;
        }
        if (pending && connected && gc::due(now, nextAttemptMs)) {
            WiFiClient client;
            WiFiClientSecure secureClient;
            if (tls) { secureClient.setCACert(GC_TLS_ROOT_CA); secureClient.setHandshakeTimeout(3); }
            HTTPClient http;
            http.setConnectTimeout(1000);
            http.setTimeout(1500);
            http.setReuse(false);
            http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
            int code = -100;
            bool acknowledged = false;
            WiFiClient& transport = tls ? static_cast<WiFiClient&>(secureClient) : client;
            if (serialize(record, body, sizeof(body)) && http.begin(transport, GC_API_URL)) {
                http.addHeader("Content-Type", "application/json");
                if (GC_API_TOKEN[0]) http.addHeader("Authorization", String("Bearer ") + GC_API_TOKEN);
                code = http.POST(reinterpret_cast<uint8_t*>(body), strlen(body));
                if (gc::storedHttp(code)) {
                    const int size = http.getSize();
                    if (size > 0 && size <= 1024) {
                        char reply[1025];
                        const size_t got = http.getStream().readBytes(reply, size);
                        acknowledged = got == static_cast<size_t>(size) &&
                            gc::validReceipt(reply, got, code, record.packet);
                    }
                    if (!acknowledged) code = -102; // 2xx alone is not durable storage confirmation.
                }
            }
            http.end();
            httpStatus.store(code);
            ++attempts;
            if (acknowledged) {
                ++delivered; lastDeliveryMs.store(millis()); pending = false;
            } else if (!gc::retryableHttp(code) || attempts >= gc::kHttpAttempts) {
                ++httpFailed;
                pending = false;
                // Permanent failure ends this sample. The next fresh sample
                // can recover immediately after backend/configuration repair.
            } else nextAttemptMs = millis() + (500UL << (attempts - 1)) + esp_random() % 251;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void lcdLine(uint8_t row, const char* text) {
    char padded[17];
    memset(padded, ' ', 16);
    padded[16] = '\0';
    const size_t length = strlen(text);
    memcpy(padded, text, length > 16 ? 16 : length);
    lcd.setCursor(0, row);
    lcd.print(padded);
}

void refreshLcd() {
    if (!lcdReady) return;
    // A disconnected/stuck I2C display must not stall the radio loop.
    Wire.beginTransmission(GC_LCD_ADDRESS);
    if (Wire.endTransmission() != 0) { lcdReady = false; return; }
    char row[32];
    bool found = false;
    for (uint8_t tries = 0; tries < gc::kMaxNodeId; ++tries) {
        displayNode = (displayNode + 1) % gc::kMaxNodeId;
        if (displayStates[displayNode].seen()) { found = true; break; }
    }
    const gc::DisplayStatus status = displayStates[displayNode].format(millis(),row,sizeof(row));
    lcdLine(0, radioReady ? row : "RF kontrol edin");
    if (!radioReady || (found && status == gc::DisplayStatus::RadioLost)) lcdLine(1,"RF veri bekliyor");
    else if (found && status == gc::DisplayStatus::SensorFault) lcdLine(1,"Sensoru kontrol");
    else if (!GC_ENABLE_HTTP) lcdLine(1,"USB aktarim");
    else lcdLine(1,gc::connectionLabel(httpEnabled.load(),wifiConnected.load(),httpStatus.load(),delivered.load()!=0,
                                     millis()-lastDeliveryMs.load()));
}

void lcdWorker(void*) {
    uint32_t nextRefreshMs = millis();
    Record record;
    for (;;) {
        if (xQueueReceive(lcdQueue, &record, pdMS_TO_TICKS(50)) == pdTRUE) {
            const uint8_t index = record.packet.nodeId - 1;
            displayStates[index].accept(record.packet,record.receivedMs);
        }
        if (gc::due(millis(), nextRefreshMs)) {
            refreshLcd();
            nextRefreshMs = millis() + 500;
        }
    }
}
} // namespace

void setup() {
    Serial.begin(115200);
    esp_task_wdt_init(12, true);
    Serial.printf("# reset_reason=%u firmware=gc-v3-mean5 active_node=%u\n", esp_reset_reason(), GC_ACTIVE_NODE_ID);
    gatewayBootId = esp_random();
    if (!gatewayBootId) gatewayBootId = 1;
    SPI.begin(18, 19, 23, 5);
    radioReady = configureRadio(radio, true);
    Serial.printf("# gateway boot=%lu radio=%s channel=%u rate=%u\n",
        static_cast<unsigned long>(gatewayBootId), radioReady ? "ok" : "error",
        gc::kRadioChannel, GC_RF_RATE_KBPS);
    httpEnabled = GC_ENABLE_HTTP && gc::validGatewayConfig(GC_WIFI_SSID, GC_WIFI_PASSWORD, GC_API_URL, GC_API_TOKEN, GC_TLS_ROOT_CA);
    if (GC_ENABLE_LCD) {
        Wire.begin(21, 22);
        Wire.setTimeOut(20);
        Wire.beginTransmission(GC_LCD_ADDRESS);
        lcdReady = Wire.endTransmission() == 0;
        if (lcdReady) { lcd.init(); lcd.backlight(); lcdLine(0,"GC Istasyon"); lcdLine(1,"Ilk olcum ~5sn"); }
        else Serial.println("# LCD not found; continuing without LCD");
    }
    serialQueue = xQueueCreate(kQueueDepth, sizeof(Record));
    httpQueue = xQueueCreate(1, sizeof(Record)); // Latest-only live stream, not a history backlog.
    if (!serialQueue || !httpQueue) {
        Serial.println("# FATAL queue allocation failed");
        radioReady = false;
        return;
    }
    if (lcdReady) {
        lcdQueue = xQueueCreate(1, sizeof(Record));
        if (!lcdQueue || xTaskCreatePinnedToCore(lcdWorker, "lcd", 3072, nullptr, 1, nullptr, 0) != pdPASS) {
            if (lcdQueue) vQueueDelete(lcdQueue);
            lcdQueue = nullptr;
            lcdReady = false;
            Serial.println("# LCD worker allocation failed; continuing without LCD");
        }
    }
    if (GC_ENABLE_HTTP && !httpEnabled)
        Serial.println("# HTTP config invalid: configure real SSID/password and backend /api/telemetry URL; HTTPS needs CA; USB remains active");
    if (httpEnabled && strncmp(GC_API_URL, "http://", 7) == 0)
        Serial.println("# LAN HTTP: transport not encrypted; never expose this configuration to the Internet");
    if (httpEnabled && xTaskCreatePinnedToCore(httpWorker, "http", 8192, nullptr, 1, nullptr, 0) != pdPASS) {
        httpEnabled = false;
        Serial.println("# HTTP worker allocation failed; USB remains active");
    }
    if (xTaskCreatePinnedToCore(serialWorker, "serial", 4096, nullptr, 1, nullptr, 0) != pdPASS) {
        Serial.println("# serial worker allocation failed; HTTP may continue");
        vQueueDelete(serialQueue);
        serialQueue = nullptr;
    }
    nextRadioCheckMs = millis() + 5000;
    gatewayReady = serialQueue != nullptr || httpEnabled;
    if (gatewayReady) esp_task_wdt_add(nullptr);
}

void loop() {
    if (!gatewayReady) { delay(20); return; }
    esp_task_wdt_reset();
    if (gc::due(millis(), nextRadioCheckMs)) {
        if (!radioReady || !radio.isChipConnected()) radioReady = configureRadio(radio, true);
        nextRadioCheckMs = millis() + 5000;
    }
    while (radioReady && radio.available()) {
        uint8_t bytes[gc::kWireSize];
        radio.read(bytes, sizeof(bytes));
        Record record;
        record.receivedMs = millis();
        if (!gc::decode(bytes, sizeof(bytes), record.packet) ||
            (GC_ACTIVE_NODE_ID && record.packet.nodeId != GC_ACTIVE_NODE_ID)) { ++rejected; continue; }
        if (!replayGuard.accept(record.packet)) { ++duplicateRf; continue; }
        if (serialQueue) enqueueLatest(serialQueue, record, serialDropped);
        if (httpEnabled) enqueueLatest(httpQueue, record, httpDropped);
        if (lcdQueue) enqueueLatest(lcdQueue, record, lcdDropped);
    }
    delay(1);
}

