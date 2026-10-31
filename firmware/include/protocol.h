#pragma once
#include <stddef.h>
#include "measurement.h"

namespace gc {
constexpr uint8_t kProtocolVersion = 3;
constexpr size_t kWireSize = 32;
struct Packet {
    uint8_t nodeId = 0;
    uint32_t bootId = 0;
    uint32_t sequence = 0;
    uint32_t measuredUptimeMs = 0;
    uint16_t windowDurationMs = 0;
    MeasurementSummary measurement;
};
inline void put16(uint8_t* out, uint16_t v) {
    out[0] = static_cast<uint8_t>(v); out[1] = static_cast<uint8_t>(v >> 8);
}
inline void put32(uint8_t* out, uint32_t v) {
    for (uint8_t i = 0; i < 4; ++i) out[i] = static_cast<uint8_t>(v >> (8 * i));
}
inline uint16_t get16(const uint8_t* in) {
    return static_cast<uint16_t>(in[0]) | (static_cast<uint16_t>(in[1]) << 8);
}
inline uint32_t get32(const uint8_t* in) {
    uint32_t v = 0;
    for (uint8_t i = 0; i < 4; ++i) v |= static_cast<uint32_t>(in[i]) << (8 * i);
    return v;
}
inline uint16_t crc16(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (uint8_t bit = 0; bit < 8; ++bit)
            crc = crc & 0x8000 ? static_cast<uint16_t>((crc << 1) ^ 0x1021) :
                                 static_cast<uint16_t>(crc << 1);
    }
    return crc;
}
inline bool validSummary(const MeasurementSummary& s) {
    if (s.attemptedPairs != kMeasurementPairs || s.validPairs > kMeasurementPairs) return false;
    for (uint8_t i = 0; i < 2; ++i) {
        if (s.validSamples[i] > kMeasurementPairs || s.validSamples[i] < s.validPairs ||
            (s.errorMasks[i] & 0xF0)) return false;
        if ((s.validSamples[i] == kMeasurementPairs) != (s.errorMasks[i] == 0)) return false;
    }
    if (s.validSamples[0] + s.validSamples[1] > kMeasurementPairs + s.validPairs) return false;
    if (!s.validPairs && s.spreadMm != kInvalidMm) return false;
    if (s.validPairs && (s.spreadMm == kInvalidMm || s.spreadMm > kMaxDistanceMm - kMinDistanceMm)) return false;
    switch (s.status) {
        case MeasurementStatus::Ok:
        case MeasurementStatus::Degraded:
            return s.validPairs >= kMinValidPairs && s.distanceMm >= kMinDistanceMm &&
                   s.distanceMm <= kMaxDistanceMm &&
                   ((s.status == MeasurementStatus::Ok) == (s.validPairs == kMeasurementPairs));
        case MeasurementStatus::TooFew:
            return s.validPairs < kMinValidPairs && s.distanceMm == kInvalidMm;
        case MeasurementStatus::Unstable:
            return false; // v3 reports changing valid ranges instead of discarding the mean.
    }
    return false;
}
inline void encode(const Packet& p, uint8_t* out) {
    out[0] = 'G'; out[1] = 'C'; out[2] = kProtocolVersion; out[3] = p.nodeId;
    put32(out + 4, p.bootId); put32(out + 8, p.sequence);
    put32(out + 12, p.measuredUptimeMs);
    const MeasurementSummary& s = p.measurement;
    put16(out + 16, s.distanceMm); put16(out + 18, s.spreadMm);
    put16(out + 20, p.windowDurationMs);
    out[22] = s.attemptedPairs; out[23] = s.validPairs;
    out[24] = s.validSamples[0]; out[25] = s.validSamples[1];
    out[26] = static_cast<uint8_t>(s.status);
    out[27] = s.errorMasks[0]; out[28] = s.errorMasks[1]; out[29] = 0;
    put16(out + 30, crc16(out, 30));
}
inline bool decode(const uint8_t* data, size_t length, Packet& output) {
    if (length != kWireSize || data[0] != 'G' || data[1] != 'C' ||
        data[2] != kProtocolVersion || get16(data + 30) != crc16(data, 30)) return false;
    Packet candidate;
    candidate.nodeId = data[3]; candidate.bootId = get32(data + 4);
    candidate.sequence = get32(data + 8); candidate.measuredUptimeMs = get32(data + 12);
    candidate.windowDurationMs = get16(data + 20);
    if (!candidate.nodeId || candidate.nodeId > kMaxNodeId || !candidate.bootId ||
        !candidate.windowDurationMs || candidate.windowDurationMs > kMaxWindowMs || data[29]) return false;
    MeasurementSummary& s = candidate.measurement;
    s.distanceMm = get16(data + 16); s.spreadMm = get16(data + 18);
    s.attemptedPairs = data[22]; s.validPairs = data[23];
    s.validSamples[0] = data[24]; s.validSamples[1] = data[25];
    s.status = static_cast<MeasurementStatus>(data[26]);
    s.errorMasks[0] = data[27]; s.errorMasks[1] = data[28];
    if (!validSummary(s)) return false;
    output = candidate;
    return true;
}
} // namespace gc

