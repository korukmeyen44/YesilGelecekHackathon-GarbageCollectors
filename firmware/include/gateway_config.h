#pragma once
// Optional file is ignored by Git. Copy gateway_config.example.h to this name.
#if __has_include("gateway_config.local.h")
#include "gateway_config.local.h"
#endif
#ifndef GC_GATEWAY_ID
#define GC_GATEWAY_ID 1
#endif
#ifndef GC_ENABLE_HTTP
#define GC_ENABLE_HTTP 0
#endif
#ifndef GC_WIFI_SSID
#define GC_WIFI_SSID ""
#endif
#ifndef GC_WIFI_PASSWORD
#define GC_WIFI_PASSWORD ""
#endif
#ifndef GC_API_URL
#define GC_API_URL ""
#endif
#ifndef GC_API_TOKEN
#define GC_API_TOKEN ""
#endif
#ifndef GC_ENABLE_LCD
#define GC_ENABLE_LCD 1
#endif
#ifndef GC_LCD_ADDRESS
#define GC_LCD_ADDRESS 0x27
#endif
static_assert(GC_GATEWAY_ID >= 1 && GC_GATEWAY_ID <= 255, "Gateway ID must fit a byte");

