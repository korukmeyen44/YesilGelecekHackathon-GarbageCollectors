#pragma once
#include <stddef.h>
#include "measurement.h"

namespace gc {
constexpr uint8_t kProtocolVersion = 1;
constexpr size_t kWireSize = 32;
struct Packet {
    uint8_t nodeId = 0;
    uint32_t bootId = 0;
    uint32_t sequence = 0;
    uint32_t measuredUptimeMs = 0;
    SensorSummary sensors[2];
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
inline bool validSummary(const SensorSummary& s) {
    if (s.validSamples > kWindowSamples || (s.errorMask & 0xF0)) return false;
    if (!s.validSamples && s.spreadMm != kInvalidMm) return false;
    if (s.validSamples && s.spreadMm == kInvalidMm) return false;
    switch (s.status) {
        case SensorStatus::Ok:
            return s.validSamples >= kMinValidSamples && s.distanceMm >= kMinDistanceMm &&
                   s.distanceMm <= kMaxDistanceMm && s.spreadMm <= kMaxSpreadMm;
        case SensorStatus::TooFew:
            return s.validSamples < kMinValidSamples && s.distanceMm == kInvalidMm;
        case SensorStatus::Unstable:
            return s.validSamples >= kMinValidSamples && s.distanceMm == kInvalidMm &&
                   s.spreadMm > kMaxSpreadMm;
    }
    return false;
}
inline void encode(const Packet& p, uint8_t* out) {
    out[0] = 'G'; out[1] = 'C'; out[2] = kProtocolVersion; out[3] = p.nodeId;
    put32(out + 4, p.bootId); put32(out + 8, p.sequence);
    put32(out + 12, p.measuredUptimeMs);
    for (uint8_t i = 0; i < 2; ++i) {
        uint8_t* s = out + 16 + i * 7;
        put16(s, p.sensors[i].distanceMm); put16(s + 2, p.sensors[i].spreadMm);
        s[4] = p.sensors[i].validSamples;
        s[5] = static_cast<uint8_t>(p.sensors[i].status); s[6] = p.sensors[i].errorMask;
    }
    put16(out + 30, crc16(out, 30));
}
inline bool decode(const uint8_t* data, size_t length, Packet& output) {
    if (length != kWireSize || data[0] != 'G' || data[1] != 'C' ||
        data[2] != kProtocolVersion || get16(data + 30) != crc16(data, 30)) return false;
    Packet candidate;
    candidate.nodeId = data[3]; candidate.bootId = get32(data + 4);
    candidate.sequence = get32(data + 8); candidate.measuredUptimeMs = get32(data + 12);
    if (!candidate.nodeId || candidate.nodeId > kMaxNodeId || !candidate.bootId) return false;
    for (uint8_t i = 0; i < 2; ++i) {
        const uint8_t* s = data + 16 + i * 7;
        candidate.sensors[i].distanceMm = get16(s);
        candidate.sensors[i].spreadMm = get16(s + 2);
        candidate.sensors[i].validSamples = s[4];
        candidate.sensors[i].status = static_cast<SensorStatus>(s[5]);
        candidate.sensors[i].errorMask = s[6];
        if (!validSummary(candidate.sensors[i])) return false;
    }
    output = candidate;
    return true;
}
} // namespace gc

