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
    char distance[8], spread[8];
    const MeasurementSummary& s = p.measurement;
    const int length = snprintf(body, capacity,
        "{\"version\":2,\"source\":\"rf\",\"node_id\":%u,\"boot_id\":%lu,\"sequence\":%lu,"
        "\"measured_uptime_ms\":%lu,\"gateway_id\":%u,\"gateway_boot_id\":%lu,"
        "\"received_gateway_ms\":%lu,\"age_ms\":%lu,"
        "\"http_dropped_total\":%lu,\"serial_dropped_total\":%lu,\"rf_rejected_total\":%lu,"
        "\"measurement\":{\"distance_mm\":%s,\"spread_mm\":%s,\"attempted_pairs\":%u,"
        "\"valid_pairs\":%u,\"valid_samples\":[%u,%u],\"status\":\"%s\","
        "\"error_masks\":[%u,%u],\"window_duration_ms\":%u}}",
        p.nodeId, static_cast<unsigned long>(p.bootId), static_cast<unsigned long>(p.sequence),
        static_cast<unsigned long>(p.measuredUptimeMs), m.gatewayId,
        static_cast<unsigned long>(m.gatewayBootId), static_cast<unsigned long>(m.receivedMs),
        static_cast<unsigned long>(m.ageMs), static_cast<unsigned long>(m.httpDropped),
        static_cast<unsigned long>(m.serialDropped), static_cast<unsigned long>(m.rejected),
        nullableMm(s.distanceMm, distance, sizeof(distance)),
        nullableMm(s.spreadMm, spread, sizeof(spread)), s.attemptedPairs, s.validPairs,
        s.validSamples[0], s.validSamples[1], statusName(s.status), s.errorMasks[0], s.errorMasks[1],
        p.windowDurationMs);
    return length > 0 && static_cast<size_t>(length) < capacity;
}
} // namespace gc
