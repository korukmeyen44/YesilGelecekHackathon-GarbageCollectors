#pragma once
#include "Arduino.h"
enum rf24_datarate_e { RF24_250KBPS, RF24_1MBPS };
constexpr uint8_t RF24_PA_LOW = 1, RF24_CRC_16 = 2;
class RF24 {
public:
    RF24(uint8_t, uint8_t) {}
    bool begin() { return true; }
    bool setDataRate(rf24_datarate_e) { return true; }
    void setChannel(uint8_t) {}
    void setAddressWidth(uint8_t) {}
    void setPALevel(uint8_t) {}
    void setCRCLength(uint8_t) {}
    void setAutoAck(bool) {}
    void setRetries(uint8_t, uint8_t) {}
    void disableDynamicPayloads() {}
    void setPayloadSize(size_t) {}
    void openReadingPipe(uint8_t, const uint8_t*) {}
    void openWritingPipe(const uint8_t*) {}
    void startListening() {}
    void stopListening() {}
    bool isChipConnected() { return true; }
    bool write(const void* buffer, size_t size) {
        fake::Transmission t;
        t.at = millis();
        t.ack = fake::failWrites == 0;
        if (fake::failWrites) --fake::failWrites;
        t.bytes.fill(0);
        memcpy(t.bytes.data(), buffer, size < 32 ? size : 32);
        fake::transmissions.push_back(t);
        return t.ack;
    }
};
