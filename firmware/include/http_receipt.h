#pragma once
#include <ArduinoJson.h>
#include "gateway_delivery.h"

namespace gc {
inline bool validReceipt(const char* text, size_t size, int code, const Packet& p) {
    if (!storedHttp(code) || !size || size > 1024) return false;
    StaticJsonDocument<1536> json;
    if (deserializeJson(json, text, size)) return false;
    JsonVariantConst id = json["measurement_id"];
    if (!id["node_id"].is<uint32_t>() || !id["boot_id"].is<uint32_t>() ||
        !id["sequence"].is<uint32_t>()) return false;
    return id["node_id"].as<uint32_t>() == p.nodeId &&
           id["boot_id"].as<uint32_t>() == p.bootId &&
           id["sequence"].as<uint32_t>() == p.sequence &&
           json["inserted"].is<bool>() && json["duplicate"].is<bool>() &&
           json["inserted"].as<bool>() == (code == 201) &&
           json["duplicate"].as<bool>() == (code == 200);
}
} // namespace gc
