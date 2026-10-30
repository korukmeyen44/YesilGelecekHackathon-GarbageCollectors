#pragma once
// Copy to gateway_config.local.h; do not commit passwords/tokens.
#define GC_ENABLE_HTTP 1
#define GC_WIFI_SSID "YOUR_2_4_GHZ_WIFI"
#define GC_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define GC_API_URL "http://192.168.1.10:8080/api/telemetry"
#define GC_API_TOKEN ""
#define GC_TLS_ROOT_CA "" // HTTPS requires a trusted PEM CA; HTTP is LAN-only.
#define GC_ACTIVE_NODE_ID 1
#define GC_GATEWAY_ID 1
#define GC_ENABLE_LCD 1
#define GC_LCD_ADDRESS 0x27

