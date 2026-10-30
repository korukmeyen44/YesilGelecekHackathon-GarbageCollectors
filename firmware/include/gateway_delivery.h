#pragma once
#include <string.h>
#include "protocol.h"

namespace gc {
constexpr uint8_t kHttpAttempts = 4;
// Pure delivery policy shared by ESP32 and host tests.
inline bool expired(uint32_t now, uint32_t received) { return now - received > kQueueTtlMs; }
inline bool retryableHttp(int code) { return code < 0 || code == 408 || code == 429 || code >= 500; }
inline bool storedHttp(int code) { return code == 200 || code == 201; }
inline uint32_t reconnectDelay(uint8_t failures, uint16_t jitter) {
    const uint8_t shift = failures > 2 ? 2 : failures;
    const uint32_t base = 10000UL << shift;
    return (base > 30000 ? 30000 : base) + jitter % 501;
}
inline bool validGatewayConfig(const char* ssid, const char* password, const char* url,
                               const char* token, const char* ca) {
    const size_t sl = strlen(ssid), pl = strlen(password);
    if (!sl || sl > 32 || strcmp(ssid, "YOUR_2_4_GHZ_WIFI") == 0 ||
        (pl && (pl < 8 || pl > 63)) || strcmp(password, "YOUR_WIFI_PASSWORD") == 0) return false;
    const bool tls = strncmp(url, "https://", 8) == 0;
    if (!tls && strncmp(url, "http://", 7) != 0) return false;
    if (tls && !ca[0]) return false; // Never silently disable certificate validation.
    const char* host = url + (tls ? 8 : 7);
    const char* path = strchr(host, '/');
    if (!path || path == host || strcmp(path, "/api/telemetry") != 0 || strlen(url) > 192) return false;
    if (strncmp(host, "localhost", 9) == 0 || strncmp(host, "127.", 4) == 0 ||
        strncmp(host, "0.0.0.0", 7) == 0 || strchr(url, '@') || strchr(url, ' ') ||
        strchr(url, '\r') || strchr(url, '\n')) return false;
    return strlen(token) <= 256 && !strchr(token, '\r') && !strchr(token, '\n');
}
class ReplayGuard {
public:
    bool accept(const Packet& p) {
        if (!p.nodeId || p.nodeId > kMaxNodeId) return false;
        const uint8_t i = p.nodeId - 1;
        if (seen_[i] && !(newer(p.bootId, boots_[i]) ||
            (p.bootId == boots_[i] && newer(p.sequence, sequences_[i])))) return false;
        boots_[i] = p.bootId; sequences_[i] = p.sequence; seen_[i] = true;
        return true;
    }
private:
    uint32_t boots_[kMaxNodeId] = {}, sequences_[kMaxNodeId] = {};
    bool seen_[kMaxNodeId] = {};
};
} // namespace gc
