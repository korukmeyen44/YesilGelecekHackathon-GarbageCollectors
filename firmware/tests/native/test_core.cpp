#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include "boot_journal.h"
#include "telemetry_json.h"

namespace {
unsigned checks = 0;
void expect(bool condition, const char* message) {
    ++checks;
    if (!condition) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}
gc::SensorSummary summary(uint16_t distance) {
    gc::SampleWindow window;
    for (uint8_t i = 0; i < 5; ++i) window.addDistance(distance);
    return window.summarize();
}
gc::Packet samplePacket() {
    gc::Packet p;
    p.nodeId = 1; p.bootId = 0x12345678UL; p.sequence = 0x01020304UL;
    p.measuredUptimeMs = 700;
    p.sensors[0] = summary(220);
    gc::SampleWindow invalid;
    invalid.addError(gc::Timeout);
    p.sensors[1] = invalid.summarize();
    return p;
}
void filterTests() {
    gc::SampleWindow w;
    w.addEchoDuration(0);
    expect(w.summarize().distanceMm == gc::kInvalidMm, "timeout must not become empty/full");
    expect(w.summarize().errorMask == gc::Timeout, "timeout reason retained");
    w.addDistance(19); w.addDistance(gc::kMaxDistanceMm + 1);
    expect(w.summarize().validSamples == 0, "reject outside nominal/configured range");
    expect(w.summarize().errorMask == (gc::Timeout | gc::TooNear | gc::TooFar), "combine reasons");
    w.reset();
    w.addEchoDuration(1166); w.addEchoDuration(1166); w.addEchoDuration(1166);
    expect(w.summarize().distanceMm == 200, "integer time-of-flight conversion in mm");
    expect(w.summarize().status == gc::SensorStatus::Ok, "three agreeing echoes accepted");
    w.reset();
    for (uint16_t v : {200, 202, 201, 700, 199}) w.addDistance(v);
    expect(w.summarize().distanceMm == 201, "isolated in-range outlier suppressed by median");
    expect(w.summarize().spreadMm == 2, "five-sample central spread");
    w.reset();
    for (uint16_t v : {200, 202, 204, 206}) w.addDistance(v);
    expect(w.summarize().distanceMm == 203, "even median avoids integer overflow");
    w.reset();
    for (uint16_t v : {100, 300, 500, 700, 900}) w.addDistance(v);
    expect(w.summarize().status == gc::SensorStatus::Unstable, "variable echoes flagged unstable");
    expect(w.summarize().distanceMm == gc::kInvalidMm, "unstable summary carries no accepted distance");
    w.reset(); w.addDistance(200); w.addDistance(200); w.addError(gc::EchoStuckHigh);
    expect(w.summarize().status == gc::SensorStatus::TooFew, "two echoes insufficient");
    expect(w.summarize().errorMask == gc::EchoStuckHigh, "stuck-high diagnosis retained");
    expect(gc::validSummary(w.summarize()), "too-few summary is a valid transport record");
    expect(summary(20).distanceMm == 20, "inclusive near boundary");
    expect(summary(gc::kMaxDistanceMm).status == gc::SensorStatus::Ok, "inclusive far boundary");
}
void protocolTests() {
    const uint8_t reference[] = {'1','2','3','4','5','6','7','8','9'};
    expect(gc::crc16(reference, sizeof(reference)) == 0x29B1, "CRC-16/CCITT-FALSE known vector");
    gc::Packet p = samplePacket(), decoded;
    uint8_t bytes[gc::kWireSize];
    gc::encode(p, bytes);
    expect(sizeof(bytes) == 32, "fixed NRF payload size");
    expect(bytes[0] == 'G' && bytes[1] == 'C' && bytes[2] == 1, "magic and version");
    expect(bytes[4] == 0x78 && bytes[7] == 0x12 && bytes[8] == 4 && bytes[11] == 1,
           "wire byte order independent of MCU struct alignment");
    expect(bytes[16] == 220 && bytes[17] == 0 && bytes[23] == 255 && bytes[24] == 255,
           "two sensor offsets and invalid sentinel");
    expect(gc::decode(bytes, sizeof(bytes), decoded), "roundtrip packet accepted");
    expect(decoded.bootId == p.bootId && decoded.sequence == p.sequence, "32-bit identity roundtrip");
    expect(decoded.sensors[1].distanceMm == gc::kInvalidMm, "invalid distance survives transmission");
    for (size_t index = 0; index < gc::kWireSize; ++index) {
        for (uint8_t bit = 0; bit < 8; ++bit) {
            bytes[index] ^= 1 << bit;
            expect(!gc::decode(bytes, sizeof(bytes), decoded), "reject every single-bit corruption");
            bytes[index] ^= 1 << bit;
        }
    }
    expect(!gc::decode(bytes, 31, decoded), "truncated payload rejected");
    p.nodeId = 4; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "unknown node rejected");
    p = samplePacket(); p.bootId = 0; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "zero boot ID rejected");
    p = samplePacket(); p.sensors[0].validSamples = 2; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "CRC-valid inconsistent sensor rejected");
    p = samplePacket(); p.sensors[0].status = static_cast<gc::SensorStatus>(99); gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "unknown sensor state rejected");
    p = samplePacket(); p.sensors[1].spreadMm = 0; gc::encode(p, bytes);
    expect(!gc::decode(bytes, sizeof(bytes), decoded), "zero valid count requires invalid spread");
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
} // namespace

int main(int argc, char** argv) {
    filterTests(); protocolTests(); bootAndTimerTests();
    char json[1024];
    gc::GatewayMetadata meta;
    meta.gatewayBootId = 17; meta.receivedMs = 1000; meta.ageMs = 5;
    expect(gc::toJson(samplePacket(), meta, json, sizeof(json)), "gateway JSON fits output buffer");
    char small[8];
    expect(!gc::toJson(samplePacket(), meta, small, sizeof(small)), "reject JSON truncation");
    if (argc == 2) {
        std::ofstream file(argv[1]);
        file << json;
        expect(file.good(), "write production gateway JSON fixture");
    }
    std::cout << "PASS " << checks << " native checks\n";
    return 0;
}

