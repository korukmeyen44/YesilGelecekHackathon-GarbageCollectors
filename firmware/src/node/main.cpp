#include <Arduino.h>
#include <EEPROM.h>
#include <SPI.h>
#include "boot_journal.h"
#include "radio_setup.h"
#if defined(ARDUINO_ARCH_AVR)
#include <avr/wdt.h>
#include <avr/io.h>
#endif

#ifndef GC_NODE_ID
#error "Build with GC_NODE_ID=1, 2 or 3"
#endif
static_assert(GC_NODE_ID >= 1 && GC_NODE_ID <= gc::kMaxNodeId, "Unknown node ID");

namespace {
constexpr uint8_t kTrig[2] = {2, 4};
constexpr uint8_t kEcho[2] = {3, 5};
constexpr uint32_t kEchoTimeoutUs =
    static_cast<uint32_t>(gc::kMaxDistanceMm) * 2000UL / 343UL + 1000UL;
RF24 radio(9, 10);
gc::MeanWindow window;
gc::Reading firstReading;
gc::Packet packet;
uint8_t wire[gc::kWireSize];
uint8_t sampleIndex = 0;
uint8_t sendAttempts = 0;
bool measuring = false;
bool sending = false;
bool radioReady = false;
uint32_t nextMeasurementMs = 0;
uint32_t nextPingMs = 0;
uint32_t nextSendMs = 0;
uint32_t nextRadioCheckMs = 0;
uint32_t ackFailures = 0;
uint32_t windowStartedMs = 0;

uint16_t nextPingGap() {
    return gc::pingGapMs(static_cast<uint16_t>(random(0, gc::kPingGapMaxMs - gc::kPingGapMinMs + 1)));
}

uint32_t nextBootId() {
    uint32_t latest = 0;
    int8_t latestSlot = -1;
    uint8_t bytes[gc::kBootSlotSize];
    for (uint8_t slot = 0; slot < gc::kBootSlotCount; ++slot) {
        for (uint8_t i = 0; i < gc::kBootSlotSize; ++i)
            bytes[i] = EEPROM.read(slot * gc::kBootSlotSize + i);
        uint32_t value = 0;
        if (gc::readBootSlot(bytes, value) && (latestSlot < 0 || gc::newer(value, latest))) {
            latest = value;
            latestSlot = slot;
        }
    }
    uint32_t next = latest + 1;
    if (!next) next = 1;
    const uint16_t address = ((latestSlot + 1) % gc::kBootSlotCount) * gc::kBootSlotSize;
    gc::makeBootSlot(next, bytes);
    EEPROM.update(address, 0); // Invalidate before writing; preserve previous slots.
    for (uint8_t i = 1; i < gc::kBootSlotSize; ++i) EEPROM.update(address + i, bytes[i]);
    EEPROM.update(address, gc::kBootCommit);
    for (uint8_t i = 0; i < gc::kBootSlotSize; ++i) bytes[i] = EEPROM.read(address + i);
    uint32_t verified = 0;
    return gc::readBootSlot(bytes, verified) && verified == next ? verified : 0;
}

gc::Reading sampleSensor(uint8_t index) {
    // A high echo before triggering is not a valid new echo.
    if (digitalRead(kEcho[index]) == HIGH) {
        return gc::invalidReading(gc::EchoStuckHigh);
    }
    digitalWrite(kTrig[index], LOW);
    delayMicroseconds(2);
    digitalWrite(kTrig[index], HIGH);
    delayMicroseconds(10);
    digitalWrite(kTrig[index], LOW);
    return gc::readingFromDuration(pulseIn(kEcho[index], HIGH, kEchoTimeoutUs));
}

void reportAttempt(bool ack) {
    Serial.print(F("# measurement bin=")); Serial.print(packet.nodeId);
    Serial.print(F(" boot=")); Serial.print(packet.bootId);
    Serial.print(F(" seq=")); Serial.print(packet.sequence);
    Serial.print(F(" mean_mm="));
    if (packet.measurement.distanceMm == gc::kInvalidMm) Serial.print(F("null"));
    else Serial.print(packet.measurement.distanceMm);
    Serial.print('/'); Serial.print(gc::statusName(packet.measurement.status));
    Serial.print(F(" pairs=")); Serial.print(packet.measurement.validPairs);
    Serial.print('/'); Serial.print(packet.measurement.attemptedPairs);
    Serial.print(F(" duration_ms=")); Serial.print(packet.windowDurationMs);
    Serial.print(F(" rf_ack=")); Serial.print(ack ? F("yes") : F("no"));
    Serial.print(F(" failures=")); Serial.println(ackFailures);
}
} // namespace

void setup() {
#if defined(ARDUINO_ARCH_AVR)
    const uint8_t resetCause = MCUSR;
    MCUSR = 0;
    wdt_disable();
#endif
    Serial.begin(115200);
#if defined(ARDUINO_ARCH_AVR)
    Serial.print(F("# reset_cause=")); Serial.println(resetCause);
#endif
    for (uint8_t i = 0; i < 2; ++i) {
        pinMode(kTrig[i], OUTPUT);
        digitalWrite(kTrig[i], LOW);
        pinMode(kEcho[i], INPUT);
    }
    packet.nodeId = GC_NODE_ID;
    packet.bootId = nextBootId();
    // Node ID guarantees a different PRNG stream even with matching startup times.
    randomSeed(packet.bootId * 2654435761UL ^ (static_cast<uint32_t>(GC_NODE_ID) << 16) ^ micros());
    radioReady = configureRadio(radio, false, GC_NODE_ID);
    Serial.print(F("# node ready; boot=")); Serial.print(packet.bootId);
    Serial.print(F(" radio=")); Serial.println(radioReady ? F("ok") : F("error"));
    if (!packet.bootId) Serial.println(F("# FATAL EEPROM verify failed; transmission disabled"));
    nextMeasurementMs = millis() + GC_NODE_ID * 150UL + random(0, 150);
    nextRadioCheckMs = millis() + 5000;
#if defined(ARDUINO_ARCH_AVR)
    wdt_enable(WDTO_8S);
#endif
}

void loop() {
#if defined(ARDUINO_ARCH_AVR)
    wdt_reset();
#endif
    if (!packet.bootId) { delay(10); return; }
    uint32_t now = millis();
    if (gc::due(now, nextRadioCheckMs)) {
        if (!radioReady || !radio.isChipConnected()) radioReady = configureRadio(radio, false, GC_NODE_ID);
        nextRadioCheckMs = millis() + 5000;
    }
    if (!measuring && !sending && gc::due(now, nextMeasurementMs)) {
        window.reset();
        sampleIndex = 0;
        measuring = true;
        windowStartedMs = now;
        nextPingMs = now + nextPingGap();
    }
    if (measuring && gc::due(now, nextPingMs)) {
        const gc::Reading reading = sampleSensor(sampleIndex % 2);
        if (sampleIndex % 2 == 0) firstReading = reading;
        else window.addPair(firstReading, reading);
        ++sampleIndex;
        // Start a fresh random quiet interval after each completed read, no catch-up burst.
        nextPingMs = millis() + nextPingGap();
        if (window.complete()) {
            measuring = false;
            packet.measuredUptimeMs = millis(); // End of the whole sample window.
            const uint32_t elapsed = packet.measuredUptimeMs - windowStartedMs;
            if (elapsed > gc::kMaxWindowMs) {
                Serial.println(F("# window overrun; discarded"));
                nextMeasurementMs = millis();
                return;
            }
            packet.windowDurationMs = static_cast<uint16_t>(elapsed);
            packet.measurement = window.summarize();
            ++packet.sequence;
            gc::encode(packet, wire);
            sending = true;
            sendAttempts = 0;
            nextSendMs = millis();
        }
    }
    if (sending && gc::due(millis(), nextSendMs)) {
        const bool ack = radioReady && radio.write(wire, sizeof(wire));
        ++sendAttempts;
        if (!ack) ++ackFailures;
        reportAttempt(ack);
        if (ack || sendAttempts >= 3) {
            sending = false;
            nextMeasurementMs = millis(); // Next group includes its own 20 random waits.
        } else {
            nextSendMs = millis() + 50 + random(0, 150);
        }
    }
}

