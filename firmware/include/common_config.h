#pragma once
#include <stdint.h>

// Both endpoints MUST use the same settings. No automatic one-sided fallback.
#ifndef GC_RF_CHANNEL
#define GC_RF_CHANNEL 76
#endif
#ifndef GC_RF_RATE_KBPS
#define GC_RF_RATE_KBPS 1000
#endif
#ifndef GC_MAX_DISTANCE_MM
#define GC_MAX_DISTANCE_MM 1200
#endif

namespace gc {
constexpr uint8_t kRadioAddress[5] = {0xE1, 0xF0, 0xF0, 0xE8, 0xE8};
constexpr uint8_t kRadioChannel = GC_RF_CHANNEL;
constexpr uint8_t kMaxNodeId = 3;
constexpr uint16_t kMinDistanceMm = 20;
constexpr uint16_t kMaxDistanceMm = GC_MAX_DISTANCE_MM;
constexpr uint8_t kMeasurementPairs = 5;
constexpr uint8_t kMinValidPairs = 3;
// Alternate sensors; 10 reads x 450 ms quiet time = ~4.5 s per report.
// Each individual sensor is triggered about once every 0.9 seconds.
constexpr uint16_t kPingGapMs = 450;
constexpr uint16_t kMaxWindowMs = 10000;
constexpr uint32_t kStaleMs = 35000;
constexpr uint32_t kQueueTtlMs = 10000;
static_assert(kPingGapMs > 60, "HC-SR04 requires an acoustic quiet interval");
static_assert(GC_RF_CHANNEL >= 2 && GC_RF_CHANNEL <= 80,
              "Choose a bench-tested channel within the intended 2.4 GHz band");
static_assert(GC_RF_RATE_KBPS == 1000 || GC_RF_RATE_KBPS == 250,
              "Supported configured rates: 1000 or 250 (plus modules only)");
static_assert(GC_MAX_DISTANCE_MM > 20 && GC_MAX_DISTANCE_MM <= 4000,
              "HC-SR04 nominal maximum is 4000 mm");

inline bool due(uint32_t now, uint32_t deadline) {
    return static_cast<int32_t>(now - deadline) >= 0;
}
inline bool newer(uint32_t candidate, uint32_t previous) {
    const uint32_t delta = candidate - previous;
    return delta != 0 && delta < 0x80000000UL;
}
} // namespace gc

