#pragma once
#include <RF24.h>
#include "common_config.h"
#include "protocol.h"

inline bool configureRadio(RF24& radio, bool receiver, uint8_t retryOffset = 0) {
    if (!radio.begin()) return false;
    const rf24_datarate_e rate = GC_RF_RATE_KBPS == 250 ? RF24_250KBPS : RF24_1MBPS;
    if (!radio.setDataRate(rate)) return false;
    radio.setChannel(gc::kRadioChannel);
    radio.setAddressWidth(5);
    radio.setPALevel(RF24_PA_LOW); // Bench default; PA+LNA supply must be verified.
    radio.setCRCLength(RF24_CRC_16);
    radio.setAutoAck(true);
    radio.setRetries(5 + retryOffset % 8, 3);
    radio.disableDynamicPayloads();
    radio.setPayloadSize(gc::kWireSize);
    if (receiver) {
        radio.openReadingPipe(1, gc::kRadioAddress);
        radio.startListening();
    } else {
        radio.openWritingPipe(gc::kRadioAddress);
        radio.stopListening();
    }
    return radio.isChipConnected();
}

