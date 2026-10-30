#pragma once
#include "protocol.h"

namespace gc {
// Power-loss resistant commit marker written last by the platform adapter.
constexpr uint8_t kBootSlotSize = 9;
constexpr uint8_t kBootSlotCount = 32;
constexpr uint8_t kBootCommit = 0xA5;
inline bool readBootSlot(const uint8_t* bytes, uint32_t& counter) {
    const uint32_t value = get32(bytes + 1);
    if (bytes[0] != kBootCommit || !value || get32(bytes + 5) != ~value) return false;
    counter = value;
    return true;
}
inline void makeBootSlot(uint32_t value, uint8_t* bytes) {
    bytes[0] = kBootCommit; put32(bytes + 1, value); put32(bytes + 5, ~value);
}
} // namespace gc

