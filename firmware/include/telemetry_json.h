#pragma once
#include <stdio.h>
#include "protocol.h"

namespace gc {
struct GatewayMetadata {
    uint8_t gatewayId = 1;
    uint32_t gatewayBootId = 1;
    uint32_t receivedMs = 0;
    uint32_t ageMs = 0;
    uint32_t httpDropped = 0;
    uint32_t serialDropped = 0;
    uint32_t rejected = 0;
};
inline const char* nullableMm(uint16_t value, char* storage, size_t capacity) {
    if (value == kInvalidMm) return "null";
    snprintf(storage, capacity, "%u", value);
    return storage;
}
inline bool toJson(const Packet& p, const GatewayMetadata& m, char* body, size_t capacity) {
    char d1[8], d2[8], s1[8], s2[8];
    const int length = snprintf(body, capacity,
        "{\"version\":1,\"source\":\"rf\",\"node_id\":%u,\"boot_id\":%lu,\"sequence\":%lu,"
        "\"measured_uptime_ms\":%lu,\"gateway_id\":%u,\"gateway_boot_id\":%lu,"
        "\"received_gateway_ms\":%lu,\"age_ms\":%lu,"
        "\"http_dropped_total\":%lu,\"serial_dropped_total\":%lu,\"rf_rejected_total\":%lu,"
        "\"sensors\":[{\"distance_mm\":%s,\"spread_mm\":%s,\"valid_samples\":%u,\"status\":\"%s\",\"error_mask\":%u},"
        "{\"distance_mm\":%s,\"spread_mm\":%s,\"valid_samples\":%u,\"status\":\"%s\",\"error_mask\":%u}]}",
        p.nodeId, static_cast<unsigned long>(p.bootId), static_cast<unsigned long>(p.sequence),
        static_cast<unsigned long>(p.measuredUptimeMs), m.gatewayId,
        static_cast<unsigned long>(m.gatewayBootId), static_cast<unsigned long>(m.receivedMs),
        static_cast<unsigned long>(m.ageMs), static_cast<unsigned long>(m.httpDropped),
        static_cast<unsigned long>(m.serialDropped), static_cast<unsigned long>(m.rejected),
        nullableMm(p.sensors[0].distanceMm, d1, sizeof(d1)),
        nullableMm(p.sensors[0].spreadMm, s1, sizeof(s1)),
        p.sensors[0].validSamples, statusName(p.sensors[0].status), p.sensors[0].errorMask,
        nullableMm(p.sensors[1].distanceMm, d2, sizeof(d2)),
        nullableMm(p.sensors[1].spreadMm, s2, sizeof(s2)),
        p.sensors[1].validSamples, statusName(p.sensors[1].status), p.sensors[1].errorMask);
    return length > 0 && static_cast<size_t>(length) < capacity;
}
} // namespace gc

