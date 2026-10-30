#pragma once
// Host-only board adapter. The real node source is exercised without hardware.
#include <stdint.h>
#include <vector>
#include <array>
#include <cstring>
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define F(value) value

namespace fake {
struct Transmission { uint32_t at; std::array<uint8_t, 32> bytes; bool ack; };
static uint32_t now = 0xFFFFF000UL, rng = 1;
static uint8_t failFirstReadings = 0, failWrites = 0;
static bool failAllFirstSensor = false;
static unsigned reads[2] = {}, currentReads[2] = {};
static std::vector<uint32_t> triggerTimes;
static std::vector<Transmission> transmissions;
}
inline uint32_t millis() { return fake::now; }
inline uint32_t micros() { return fake::now * 1000UL; }
inline void delay(unsigned long ms) { fake::now += ms; }
inline void delayMicroseconds(unsigned int) {}
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t pin, uint8_t value) {
    if ((pin == 2 || pin == 4) && value == HIGH) fake::triggerTimes.push_back(millis());
}
inline int digitalRead(uint8_t) { return LOW; }
inline uint32_t pulseIn(uint8_t pin, uint8_t, uint32_t timeout) {
    const uint8_t sensor = pin == 3 ? 0 : 1;
    ++fake::reads[sensor];
    ++fake::currentReads[sensor];
    if (!sensor && (fake::failAllFirstSensor || fake::currentReads[0] <= fake::failFirstReadings)) {
        fake::now += (timeout + 999) / 1000;
        return 0;
    }
    fake::now += sensor ? 2 : 1;
    return sensor ? 1749 : 583; // 300 mm and 100 mm respectively.
}
inline void randomSeed(uint32_t seed) { fake::rng = seed; }
inline long random(long low, long high) {
    fake::rng = fake::rng * 1664525UL + 1013904223UL;
    return low + (fake::rng >> 8) % (high - low);
}
struct FakeSerial {
    void begin(unsigned long) {}
    template<class T> void print(T) {}
    template<class T> void println(T) {}
};
static FakeSerial Serial;
