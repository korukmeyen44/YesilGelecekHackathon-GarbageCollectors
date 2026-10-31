#pragma once
#include <stdio.h>
#include "protocol.h"

namespace gc {
enum class DisplayStatus : uint8_t { Waiting, Current, SensorFault, RadioLost };

// A bad group never becomes 0 mm and never silently renews the last good value.
class DisplayState {
public:
    bool seen() const { return seen_; }
    bool accept(const Packet& p, uint32_t received) {
        if (seen_ && !(newer(p.bootId, latest_.bootId) ||
            (p.bootId == latest_.bootId && newer(p.sequence, latest_.sequence)))) return false;
        if (seen_ && p.bootId != latest_.bootId) hasGood_ = false;
        latest_ = p; received_ = received; seen_ = true;
        if (p.measurement.distanceMm != kInvalidMm) {
            goodMm_ = p.measurement.distanceMm; goodAt_ = received; hasGood_ = true;
        }
        return true;
    }
    DisplayStatus format(uint32_t now, char* row, size_t size) const {
        if (!seen_) { snprintf(row,size,"Olcum bekleniyor"); return DisplayStatus::Waiting; }
        const bool lost = now - received_ > kStaleMs;
        if (!lost && latest_.measurement.distanceMm != kInvalidMm) {
            snprintf(row,size,"K%u Ort:%umm",latest_.nodeId,latest_.measurement.distanceMm);
            return DisplayStatus::Current;
        }
        if (hasGood_) snprintf(row,size,"Son %umm %lus",goodMm_,static_cast<unsigned long>((now-goodAt_)/1000));
        else snprintf(row,size,lost ? "Kutu bekleniyor" : "Olcum alinamadi");
        return lost ? DisplayStatus::RadioLost : DisplayStatus::SensorFault;
    }
private:
    Packet latest_;
    uint32_t received_ = 0, goodAt_ = 0;
    uint16_t goodMm_ = kInvalidMm;
    bool seen_ = false, hasGood_ = false;
};

inline const char* connectionLabel(bool httpEnabled, bool wifi, int code, bool delivered, uint32_t ackAge) {
    if (!httpEnabled) return "API ayari gerek";
    if (!wifi) return "WiFi baglaniyor";
    if (code == 401 || code == 403) return "API anahtar hata";
    if (code == 404) return "API adres hata";
    if ((code == 200 || code == 201) && delivered && ackAge <= kStaleMs) return "WiFi OK API OK";
    if (!code) return "API bekleniyor";
    return "Sunucu kontrol";
}
} // namespace gc
