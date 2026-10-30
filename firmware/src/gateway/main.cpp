#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <LiquidCrystal_I2C.h>
#include <esp_system.h>
#include <atomic>
#include "gateway_config.h"
#include "radio_setup.h"
#include "telemetry_json.h"

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
std::atomic<int> httpStatus(0);
std::atomic<bool> wifiConnected(false);
uint32_t gatewayBootId = 0;
std::atomic<bool> radioReady(false), lcdReady(false), httpEnabled(false);
bool gatewayReady = false;
Record lastRecords[gc::kMaxNodeId];
bool seen[gc::kMaxNodeId] = {};
uint32_t nextRadioCheckMs = 0;
uint8_t displayNode = 0;

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
            Serial.printf("# stats rf_rejected=%lu serial_dropped=%lu http_dropped=%lu http_expired=%lu http_failed=%lu wifi=%u http=%d lcd=%u lcd_dropped=%lu\n",
                static_cast<unsigned long>(rejected.load()), static_cast<unsigned long>(serialDropped.load()),
                static_cast<unsigned long>(httpDropped.load()), static_cast<unsigned long>(httpExpired.load()),
                static_cast<unsigned long>(httpFailed.load()), wifiConnected.load(), httpStatus.load(),
                lcdReady.load(), static_cast<unsigned long>(lcdDropped.load()));
            lastStatsMs = millis();
        }
    }
}

void httpWorker(void*) {
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(GC_WIFI_SSID, GC_WIFI_PASSWORD);
    uint32_t lastConnectMs = millis();
    Record record;
    bool pending = false;
    uint8_t attempts = 0;
    uint32_t nextAttemptMs = 0;
    char body[1024];
    for (;;) {
        const uint32_t now = millis();
        const bool connected = WiFi.status() == WL_CONNECTED;
        wifiConnected.store(connected);
        if (!connected && now - lastConnectMs >= 10000) {
            WiFi.reconnect();
            lastConnectMs = now;
        }
        if (!pending && xQueueReceive(httpQueue, &record, 0) == pdTRUE) {
            pending = true;
            attempts = 0;
            nextAttemptMs = now;
        }
        if (pending && now - record.receivedMs > gc::kQueueTtlMs) {
            ++httpExpired;
            pending = false;
        }
        if (pending && connected && gc::due(now, nextAttemptMs)) {
            WiFiClient client;
            HTTPClient http;
            http.setConnectTimeout(1000);
            http.setTimeout(1500);
            http.setReuse(false);
            int code = -100;
            if (serialize(record, body, sizeof(body)) && http.begin(client, GC_API_URL)) {
                http.addHeader("Content-Type", "application/json");
                if (GC_API_TOKEN[0]) http.addHeader("Authorization", String("Bearer ") + GC_API_TOKEN);
                code = http.POST(reinterpret_cast<uint8_t*>(body), strlen(body));
            }
            http.end();
            httpStatus.store(code);
            ++attempts;
            if (code >= 200 && code < 300) pending = false;
            else if ((code >= 400 && code < 500 && code != 408 && code != 429) || attempts >= 4) {
                ++httpFailed;
                pending = false;
            } else nextAttemptMs = millis() + (500UL << (attempts - 1));
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
        if (seen[displayNode]) { found = true; break; }
    }
    if (!radioReady) lcdLine(0, "RF BAGLANTI HATA");
    else if (!found) lcdLine(0, "RF bekleniyor");
    else {
        const Record& r = lastRecords[displayNode];
        if (millis() - r.receivedMs > gc::kStaleMs) snprintf(row, sizeof(row), "K%u VERI ESKI", r.packet.nodeId);
        else {
            char distance[8];
            snprintf(row, sizeof(row), "K%u %smm %u/10", r.packet.nodeId,
                gc::nullableMm(r.packet.measurement.distanceMm, distance, sizeof(distance)),
                r.packet.measurement.validPairs);
        }
        lcdLine(0, row);
    }
    if (!httpEnabled) lcdLine(1, "USB JSON aktif");
    else {
        snprintf(row, sizeof(row), "W:%s H:%d Q:%u", wifiConnected.load() ? "OK" : "--",
                 httpStatus.load(), static_cast<unsigned>(uxQueueMessagesWaiting(httpQueue)));
        lcdLine(1, row);
    }
}

void lcdWorker(void*) {
    uint32_t nextRefreshMs = millis();
    Record record;
    for (;;) {
        if (xQueueReceive(lcdQueue, &record, pdMS_TO_TICKS(50)) == pdTRUE) {
            const uint8_t index = record.packet.nodeId - 1;
            if (!seen[index] || gc::newer(record.packet.bootId, lastRecords[index].packet.bootId) ||
                (record.packet.bootId == lastRecords[index].packet.bootId &&
                 gc::newer(record.packet.sequence, lastRecords[index].packet.sequence))) {
                lastRecords[index] = record;
                seen[index] = true;
            }
        }
        if (gc::due(millis(), nextRefreshMs)) {
            refreshLcd();
            nextRefreshMs = millis() + 1000;
        }
    }
}
} // namespace

void setup() {
    Serial.begin(115200);
    gatewayBootId = esp_random();
    if (!gatewayBootId) gatewayBootId = 1;
    SPI.begin(18, 19, 23, 5);
    radioReady = configureRadio(radio, true);
    Serial.printf("# gateway boot=%lu radio=%s channel=%u rate=%u\n",
        static_cast<unsigned long>(gatewayBootId), radioReady ? "ok" : "error",
        gc::kRadioChannel, GC_RF_RATE_KBPS);
    if (GC_ENABLE_LCD) {
        Wire.begin(21, 22);
        Wire.setTimeOut(20);
        Wire.beginTransmission(GC_LCD_ADDRESS);
        lcdReady = Wire.endTransmission() == 0;
        if (lcdReady) { lcd.init(); lcd.backlight(); }
        else Serial.println("# LCD not found; continuing without LCD");
    }
    serialQueue = xQueueCreate(kQueueDepth, sizeof(Record));
    httpQueue = xQueueCreate(kQueueDepth, sizeof(Record));
    if (!serialQueue || !httpQueue) {
        Serial.println("# FATAL queue allocation failed");
        radioReady = false;
        return;
    }
    if (lcdReady) {
        lcdQueue = xQueueCreate(kQueueDepth, sizeof(Record));
        if (!lcdQueue || xTaskCreatePinnedToCore(lcdWorker, "lcd", 3072, nullptr, 1, nullptr, 0) != pdPASS) {
            if (lcdQueue) vQueueDelete(lcdQueue);
            lcdQueue = nullptr;
            lcdReady = false;
            Serial.println("# LCD worker allocation failed; continuing without LCD");
        }
    }
    httpEnabled = GC_ENABLE_HTTP && GC_WIFI_SSID[0] && strncmp(GC_API_URL, "http://", 7) == 0;
    if (GC_ENABLE_HTTP && !httpEnabled)
        Serial.println("# HTTP config invalid: SSID and local http:// URL required; USB remains active");
    if (httpEnabled && xTaskCreatePinnedToCore(httpWorker, "http", 8192, nullptr, 1, nullptr, 0) != pdPASS) {
        httpEnabled = false;
        Serial.println("# HTTP worker allocation failed; USB remains active");
    }
    if (xTaskCreatePinnedToCore(serialWorker, "serial", 4096, nullptr, 1, nullptr, 0) != pdPASS) {
        // Do not receive packets silently if the default USB output is unavailable.
        Serial.println("# FATAL serial worker allocation failed");
        vQueueDelete(serialQueue);
        serialQueue = nullptr;
    }
    nextRadioCheckMs = millis() + 5000;
    gatewayReady = serialQueue != nullptr;
}

void loop() {
    if (!gatewayReady) { delay(20); return; }
    if (gc::due(millis(), nextRadioCheckMs)) {
        if (!radioReady || !radio.isChipConnected()) radioReady = configureRadio(radio, true);
        nextRadioCheckMs = millis() + 5000;
    }
    while (radioReady && radio.available()) {
        uint8_t bytes[gc::kWireSize];
        radio.read(bytes, sizeof(bytes));
        Record record;
        record.receivedMs = millis();
        if (!gc::decode(bytes, sizeof(bytes), record.packet)) { ++rejected; continue; }
        enqueueLatest(serialQueue, record, serialDropped);
        if (httpEnabled) enqueueLatest(httpQueue, record, httpDropped);
        if (lcdQueue) enqueueLatest(lcdQueue, record, lcdDropped);
    }
    delay(1);
}

