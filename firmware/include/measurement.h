#pragma once
#include "common_config.h"

namespace gc {
constexpr uint16_t kInvalidMm = 0xFFFF;
enum class SensorStatus : uint8_t { Ok = 0, TooFew = 1, Unstable = 2 };
enum SampleError : uint8_t {
    Timeout = 1, TooNear = 2, TooFar = 4, EchoStuckHigh = 8
};

struct SensorSummary {
    uint16_t distanceMm = kInvalidMm;
    uint16_t spreadMm = kInvalidMm;
    uint8_t validSamples = 0;
    SensorStatus status = SensorStatus::TooFew;
    uint8_t errorMask = 0;
};

inline const char* statusName(SensorStatus status) {
    switch (status) {
        case SensorStatus::Ok: return "ok";
        case SensorStatus::TooFew: return "too_few";
        case SensorStatus::Unstable: return "unstable";
    }
    return "unknown";
}

class SampleWindow {
public:
    void reset() { count_ = 0; errors_ = 0; }
    void addError(uint8_t error) { errors_ |= error; }
    void addDistance(uint16_t mm) {
        if (mm < kMinDistanceMm) { errors_ |= TooNear; return; }
        if (mm > kMaxDistanceMm) { errors_ |= TooFar; return; }
        if (count_ < kWindowSamples) values_[count_++] = mm;
    }
    void addEchoDuration(uint32_t microseconds) {
        if (microseconds == 0) { errors_ |= Timeout; return; }
        // Speed of sound assumed 343 m/s. Keep the multiply in 32 bits.
        if (microseconds > 30000UL) { errors_ |= TooFar; return; }
        addDistance(static_cast<uint16_t>((microseconds * 343UL + 1000UL) / 2000UL));
    }
    SensorSummary summarize() const {
        SensorSummary result;
        result.validSamples = count_;
        result.errorMask = errors_;
        if (!count_) return result;
        uint16_t sorted[kWindowSamples];
        for (uint8_t i = 0; i < count_; ++i) {
            sorted[i] = values_[i];
            for (uint8_t j = i; j > 0 && sorted[j] < sorted[j - 1]; --j) {
                const uint16_t tmp = sorted[j];
                sorted[j] = sorted[j - 1];
                sorted[j - 1] = tmp;
            }
        }
        // With all five echoes, ignore one extreme at each end for spread only.
        // With three/four echoes, require the entire surviving set to agree.
        const uint8_t low = count_ == 5 ? 1 : 0;
        const uint8_t high = count_ == 5 ? 3 : count_ - 1;
        result.spreadMm = sorted[high] - sorted[low];
        if (count_ < kMinValidSamples) return result;
        if (result.spreadMm > kMaxSpreadMm) {
            result.status = SensorStatus::Unstable;
            return result;
        }
        result.status = SensorStatus::Ok;
        result.distanceMm = count_ % 2 ? sorted[count_ / 2] :
            static_cast<uint16_t>((static_cast<uint32_t>(sorted[count_ / 2 - 1]) +
                                   sorted[count_ / 2]) / 2);
        return result;
    }
private:
    uint16_t values_[kWindowSamples] = {};
    uint8_t count_ = 0;
    uint8_t errors_ = 0;
};
} // namespace gc

