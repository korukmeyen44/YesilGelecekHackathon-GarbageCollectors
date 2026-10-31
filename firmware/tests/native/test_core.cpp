#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include "boot_journal.h"
#include "telemetry_json.h"
#include "lcd_status.h"

namespace {
unsigned checks = 0;
void expect(bool condition, const char* message) {
    ++checks;
    if (!condition) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
gc::MeasurementSummary summary(uint16_t first, uint16_t second, uint8_t good = 5) {
    gc::MeanWindow window;
    for (uint8_t i = 0; i < gc::kMeasurementPairs; ++i)
        window.addPair(i < good ? gc::readingFromDistance(first) : gc::invalidReading(gc::Timeout),
                       gc::readingFromDistance(second));
    return window.summarize();
}
gc::Packet samplePacket() {
    gc::Packet p;
    p.nodeId = 1; p.bootId = 0x12345678UL; p.sequence = 0x01020304UL;
    p.measuredUptimeMs = 5000; p.windowDurationMs = 4500;
    p.measurement = summary(200, 240, 4);
    return p;
}
void measurementTests() {
    expect(gc::readingFromDuration(0).errorMask == gc::Timeout, "timeout stays invalid");
    expect(gc::readingFromDistance(19).errorMask == gc::TooNear, "near bound");
    expect(gc::readingFromDistance(gc::kMaxDistanceMm + 1).errorMask == gc::TooFar, "far bound");
    expect(gc::readingFromDuration(1166).distanceMm == 200, "time-of-flight conversion");
    expect(gc::readingFromDuration(40000).errorMask == gc::TooFar, "duration overflow guarded");
    expect(summary(80, 360).distanceMm == 220, "two different sensor ranges are averaged on node");
    expect(summary(80, 360).status == gc::MeasurementStatus::Ok, "spatial difference does not reject mean");
    gc::MeanWindow w;
    for (uint8_t i = 0; i < 4; ++i) w.addPair(gc::readingFromDistance(200), gc::readingFromDistance(200));
    expect(!w.complete() && w.summarize().distanceMm == gc::kInvalidMm, "no report before five pairs");
    w.addPair(gc::readingFromDistance(280), gc::readingFromDistance(280));
    expect(w.complete() && w.summarize().distanceMm == 216, "arithmetic mean, not median");
    expect(w.summarize().spreadMm == 80, "temporal pair mean spread inclusive threshold");
    w.addPair(gc::readingFromDistance(1200), gc::readingFromDistance(1200));
    expect(w.summarize().distanceMm == 216, "exactly five attempts; extra samples cannot change group");
    w.reset();
    for (uint8_t i = 0; i < 5; ++i)
        w.addPair(gc::readingFromDistance(i < 2 ? 200 : 201), gc::readingFromDistance(i < 2 ? 201 : 202));
    expect(w.summarize().distanceMm == 201, "round once after all raw paired sums");
    expect(summary(200, 240, 3).status == gc::MeasurementStatus::Degraded, "three valid pairs accepted degraded");
    expect(summary(200, 240, 3).distanceMm == 220, "invalid readings never count as zero");
    expect(summary(200, 240, 2).distanceMm == gc::kInvalidMm, "two valid pairs insufficient");
    expect(summary(200, 240, 0).validSamples[1] == 5, "per-sensor diagnostics retained without distances");
    expect(summary(200, 240, 0).distanceMm == gc::kInvalidMm, "lone sensor cannot substitute combined pair");
    expect(gc::validSummary(summary(200, 240, 0)), "invalid window still transportable");
    w.reset();
    for (uint8_t i = 0; i < 5; ++i)
        w.addPair(gc::readingFromDistance(i < 2 ? 100 : 300), gc::readingFromDistance(i < 2 ? 100 : 300));
    expect(w.summarize().status == gc::MeasurementStatus::Ok, "moving valid readings remain transportable");
    expect(w.summarize().distanceMm == 220 && w.summarize().spreadMm == 200, "change is averaged, not turned into null");
    expect(summary(20, 20).distanceMm == 20, "minimum distance");
    expect(summary(gc::kMaxDistanceMm, gc::kMaxDistanceMm).distanceMm == gc::kMaxDistanceMm,
           "32-bit accumulation avoids AVR 16-bit overflow");
    expect(gc::kPingGapMs > 60, "quiet gap exceeds HC-SR04 acoustic minimum");
    expect(2UL * gc::kMeasurementPairs * gc::kPingGapMs == 4500, "five pairs take about 4.5 seconds");
}
void protocolTests() {
    const uint8_t reference[] = {'1','2','3','4','5','6','7','8','9'};
    expect(gc::crc16(reference, sizeof(reference)) == 0x29B1, "known CRC vector");
    gc::Packet p = samplePacket(), decoded;
    uint8_t bytes[gc::kWireSize];
    gc::encode(p, bytes);
    expect(sizeof(bytes) == 32 && bytes[2] == 3, "v3 fixed 32-byte payload");
    expect(bytes[4] == 0x78 && bytes[7] == 0x12 && bytes[8] == 4, "little-endian identity");
    expect(bytes[16] == 220 && bytes[17] == 0 && gc::get16(bytes + 20) == 4500,
           "single combined mean and actual window duration offsets");
    expect(bytes[22] == 5 && bytes[23] == 4 && bytes[24] == 4 && bytes[25] == 5,
           "group diagnostics offsets");
    expect(gc::decode(bytes, sizeof(bytes), decoded), "v3 packet accepted");
    expect(decoded.measurement.distanceMm == 220 && decoded.sequence == p.sequence, "roundtrip");
    for (size_t index = 0; index < gc::kWireSize; ++index) {
        for (uint8_t bit = 0; bit < 8; ++bit) {
            bytes[index] ^= 1 << bit;
            expect(!gc::decode(bytes, sizeof(bytes), decoded), "single bit corruption rejected");
            bytes[index] ^= 1 << bit;
        }
    }
    bytes[2] = 1; gc::put16(bytes + 30, gc::crc16(bytes, 30));
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "old v1 rejected even with valid CRC");
    gc::encode(p, bytes);
    expect(!gc::decode(bytes, 31, decoded), "truncated packet rejected");
    p.nodeId = 4; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "unknown node rejected");
    p = samplePacket(); p.bootId = 0; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "zero boot rejected");
    p = samplePacket(); p.windowDurationMs = 0; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "missing duration rejected");
    p = samplePacket(); p.measurement.status = gc::MeasurementStatus::Ok; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "incomplete sample set cannot claim ok");
    p = samplePacket(); p.measurement.validPairs = 3; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "inconsistent paired sample counts rejected");
    p = samplePacket(); p.measurement.errorMasks[0] = 0; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "failed samples require error reason");
    p = samplePacket(); p.measurement = summary(200, 240, 0); gc::encode(p, bytes);
    expect(gc::decode(bytes, sizeof(bytes), decoded) && decoded.measurement.distanceMm == gc::kInvalidMm,
           "invalid summary remains invalid through protocol");
}
void bootAndTimerTests() {
    uint8_t slot[gc::kBootSlotSize];
    uint32_t output = 0;
    memset(slot, 0xFF, sizeof(slot));
    expect(!gc::readBootSlot(slot, output), "erased EEPROM slot invalid");
    gc::makeBootSlot(42, slot);
    expect(gc::readBootSlot(slot, output) && output == 42, "committed boot slot accepted");
    slot[0] = 0;
    expect(!gc::readBootSlot(slot, output), "interrupted uncommitted write rejected");
    gc::makeBootSlot(42, slot); slot[3] ^= 4;
    expect(!gc::readBootSlot(slot, output), "damaged boot counter rejected");
    expect(gc::newer(1, 0xFFFFFFFFUL), "counter wraparound");
    expect(!gc::newer(5, 5) && !gc::newer(4, 5), "duplicate and old counters");
    expect(gc::due(4, 0xFFFFFFFEUL), "deadline across millis rollover");
    expect(!gc::due(0xFFFFFFFEUL, 4), "future deadline across millis rollover");
}
void lcdTests() {
    gc::DisplayState display;
    char row[17];
    expect(display.format(0,row,sizeof(row)) == gc::DisplayStatus::Waiting, "startup waits for a real group");
    expect(!std::strstr(row,"null") && !std::strstr(row,"mm"), "startup never prints null mm");
    gc::Packet p = samplePacket();
    expect(display.accept(p,1000), "first LCD group accepted");
    expect(display.format(1100,row,sizeof(row)) == gc::DisplayStatus::Current && std::strstr(row,"220mm"), "LCD shows actual average");
    expect(!display.accept(p,34000), "duplicate cannot renew LCD freshness");
    ++p.sequence;p.measurement=summary(200,240,0);
    display.accept(p,5500);
    expect(display.format(6000,row,sizeof(row)) == gc::DisplayStatus::SensorFault, "failed group has an explicit sensor state");
    expect(std::strstr(row,"Son 220mm 5s"), "last value is labelled with its real age");
    expect(display.format(41000,row,sizeof(row)) == gc::DisplayStatus::RadioLost, "RF outage remains distinguishable from sensor failure");
    ++p.bootId;display.accept(p,42000);
    display.format(42000,row,sizeof(row));
    expect(!std::strstr(row,"220mm"), "reboot cannot relabel previous session distance as current");
    gc::DisplayState rollover;p.measurement=summary(200,240);
    rollover.accept(p,0xffffff00UL);
    expect(rollover.format(1000,row,sizeof(row)) == gc::DisplayStatus::Current, "LCD freshness survives millis rollover");
    expect(std::strcmp(gc::connectionLabel(true,false,0,false,0),"WiFi baglaniyor") == 0, "Wi-Fi state is readable");
    expect(std::strcmp(gc::connectionLabel(true,true,201,true,10),"WiFi OK API OK") == 0, "API OK requires a confirmed recent delivery");
    expect(std::strcmp(gc::connectionLabel(true,true,0,false,0),"API bekleniyor") == 0, "no premature API success");
    expect(std::strcmp(gc::connectionLabel(true,true,401,true,10),"API anahtar hata") == 0, "authentication failure cannot show API OK");
}
} // namespace

int main(int argc, char** argv) {
    measurementTests(); protocolTests(); bootAndTimerTests(); lcdTests();
    char json[1024];
    gc::GatewayMetadata meta;
    meta.gatewayBootId = 17; meta.receivedMs = 11000; meta.ageMs = 5;
    expect(gc::toJson(samplePacket(), meta, json, sizeof(json)), "gateway JSON fits buffer");
    expect(std::strstr(json, "\"measurement\"") && !std::strstr(json, "\"sensors\""),
           "wire JSON exposes a single mean only");
    char small[8];
    expect(!gc::toJson(samplePacket(), meta, small, sizeof(small)), "truncated JSON rejected");
    if (argc == 2) {
        std::ofstream file(argv[1]); file << json;
        expect(file.good(), "write production JSON fixture");
    }
    std::cout << "PASS " << checks << " native checks\n";
    return 0;
}
