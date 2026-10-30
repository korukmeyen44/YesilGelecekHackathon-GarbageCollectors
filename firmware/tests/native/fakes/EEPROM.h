#pragma once
#include "Arduino.h"
struct FakeEEPROM {
    uint8_t memory[1024];
    FakeEEPROM() { memset(memory, 0xFF, sizeof(memory)); }
    uint8_t read(uint16_t address) { return memory[address]; }
    void update(uint16_t address, uint8_t value) { memory[address] = value; }
};
static FakeEEPROM EEPROM;
