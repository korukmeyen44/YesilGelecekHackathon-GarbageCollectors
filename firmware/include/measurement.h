#pragma once
#include "common_config.h"

namespace gc {
constexpr uint16_t kInvalidMm = 0xFFFF;
enum class MeasurementStatus : uint8_t { Ok = 0, TooFew = 1, Unstable = 2, Degraded = 3 };
enum SampleError : uint8_t { Timeout = 1, TooNear = 2, TooFar = 4, EchoStuckHigh = 8 };

struct Reading {
    uint16_t distanceMm = kInvalidMm;
    uint8_t errorMask = 0;
};
inline Reading invalidReading(uint8_t error) {
    Reading r; r.errorMask = error; return r;
}
inline Reading readingFromDistance(uint16_t mm) {
    if (mm < kMinDistanceMm) return invalidReading(TooNear);
    if (mm > kMaxDistanceMm) return invalidReading(TooFar);
    Reading r; r.distanceMm = mm; return r;
}
inline Reading readingFromDuration(uint32_t microseconds) {
    if (!microseconds) return invalidReading(Timeout);
    if (microseconds > 30000UL) return invalidReading(TooFar);
    return readingFromDistance(static_cast<uint16_t>((microseconds * 343UL + 1000UL) / 2000UL));
}

struct MeasurementSummary {
    uint16_t distanceMm = kInvalidMm;
    uint16_t spreadMm = kInvalidMm;
    uint8_t attemptedPairs = 0;
    uint8_t validPairs = 0;
    uint8_t validSamples[2] = {};
    MeasurementStatus status = MeasurementStatus::TooFew;
    uint8_t errorMasks[2] = {};
};
inline const char* statusName(MeasurementStatus status) {
    switch (status) {
        case MeasurementStatus::Ok: return "ok";
        case MeasurementStatus::TooFew: return "too_few";
        case MeasurementStatus::Unstable: return "unstable";
        case MeasurementStatus::Degraded: return "degraded";
    }
    return "unknown";
}

class MeanWindow {
public:
    void reset() {
        summary_ = MeasurementSummary(); sumMm_ = 0; minPairSum_ = 0xFFFF; maxPairSum_ = 0;
    }
    bool complete() const { return summary_.attemptedPairs == kMeasurementPairs; }
    void addPair(const Reading& first, const Reading& second) {
        if (complete()) return;
        ++summary_.attemptedPairs;
        const Reading readings[2] = {first, second};
        for (uint8_t i = 0; i < 2; ++i) {
            summary_.errorMasks[i] |= readings[i].errorMask;
            if (readings[i].distanceMm != kInvalidMm) ++summary_.validSamples[i];
        }
        // Equal sensor weighting: never replace a two-sensor pair with a lone echo.
        if (first.distanceMm == kInvalidMm || second.distanceMm == kInvalidMm) return;
        const uint16_t pairSum = first.distanceMm + second.distanceMm;
        sumMm_ += pairSum;
        ++summary_.validPairs;
        if (pairSum < minPairSum_) minPairSum_ = pairSum;
        if (pairSum > maxPairSum_) maxPairSum_ = pairSum;
    }
    MeasurementSummary summarize() const {
        MeasurementSummary result = summary_;
        if (result.validPairs) result.spreadMm = (maxPairSum_ - minPairSum_ + 1) / 2;
        if (!complete() || result.validPairs < kMinValidPairs) return result;
        if (result.spreadMm > kMaxSpreadMm) {
            result.status = MeasurementStatus::Unstable;
            return result;
        }
        const uint8_t denominator = result.validPairs * 2;
        // Arithmetic mean of complete pairs; round once after accumulation.
        result.distanceMm = static_cast<uint16_t>((sumMm_ + denominator / 2) / denominator);
        result.status = result.validPairs == kMeasurementPairs ?
            MeasurementStatus::Ok : MeasurementStatus::Degraded;
        return result;
    }
private:
    MeasurementSummary summary_;
    uint32_t sumMm_ = 0;
    uint16_t minPairSum_ = 0xFFFF;
    uint16_t maxPairSum_ = 0;
};
} // namespace gc
