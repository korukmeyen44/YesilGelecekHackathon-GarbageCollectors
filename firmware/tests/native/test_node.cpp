#include <cstdlib>
#include <iostream>
#define GC_NODE_ID 1
#include "../../src/node/main.cpp"

namespace {
unsigned checks = 0;
void expect(bool condition, const char* message) {
    ++checks;
    if (!condition) { std::cerr << "FAIL node: " << message << '\n'; std::exit(1); }
}
void untilTransmission(size_t target) {
    const uint32_t started = millis();
    while (fake::transmissions.size() < target && millis() - started < 20000) {
        loop();
        ++fake::now;
    }
    expect(fake::transmissions.size() == target, "bounded report time");
}
gc::Packet decodeTransmission(size_t index) {
    gc::Packet p;
    const fake::Transmission& tx = fake::transmissions[index];
    expect(gc::decode(tx.bytes.data(), tx.bytes.size(), p), "actual node emits valid v3 packet");
    return p;
}
void prepareNextGroup() { fake::currentReads[0] = fake::currentReads[1] = 0; }
}

int main() {
    setup(); // Starts near millis rollover; all subsequent timings cross it.
    untilTransmission(1);
    gc::Packet first = decodeTransmission(0);
    expect(first.measurement.distanceMm == 200, "actual firmware sends the two-sensor arithmetic mean");
    expect(first.measurement.validPairs == 5, "exactly five complete pairs");
    expect(fake::reads[0] == 5 && fake::reads[1] == 5, "five readings per sensor, not five combined readings");
    expect(first.windowDurationMs >= 4500 && first.windowDurationMs <= 4600, "4.5 second acquisition window");
    expect(first.measuredUptimeMs == fake::transmissions[0].at, "window end timestamp");

    prepareNextGroup(); fake::failFirstReadings = 2;
    untilTransmission(2);
    gc::Packet second = decodeTransmission(1);
    expect(second.measurement.distanceMm == 200 && second.measurement.validPairs == 3,
           "three surviving pairs are averaged without zero substitution");
    expect(second.measurement.status == gc::MeasurementStatus::Degraded, "partial group diagnosed");
    expect(fake::reads[0] == 10 && fake::reads[1] == 10, "failed readings count toward fixed group size");
    expect(fake::transmissions[1].at - fake::transmissions[0].at == static_cast<uint32_t>(second.windowDurationMs) + 1U,
           "no old three-second gap between groups");

    prepareNextGroup(); fake::failAllFirstSensor = true;
    untilTransmission(3);
    gc::Packet third = decodeTransmission(2);
    expect(third.measurement.distanceMm == gc::kInvalidMm && third.measurement.validPairs == 0,
           "one failed sensor cannot become a fake two-sensor average");
    expect(fake::reads[0] == 15 && fake::reads[1] == 15, "timeouts do not extend group sample count");

    prepareNextGroup(); fake::failAllFirstSensor = false; fake::failFirstReadings = 0;
    fake::failWrites = 2;
    untilTransmission(6);
    const gc::Packet fourth = decodeTransmission(3);
    expect(fourth.measurement.distanceMm == 200, "next group recovers after timeout");
    expect(fake::transmissions[3].bytes == fake::transmissions[4].bytes &&
           fake::transmissions[4].bytes == fake::transmissions[5].bytes, "RF retries preserve mean and identity");
    expect(fake::reads[0] == 20 && fake::reads[1] == 20, "RF retries do not resample");
    for (size_t i = 1; i < fake::triggerTimes.size(); ++i)
        expect(fake::triggerTimes[i] - fake::triggerTimes[i - 1] >= gc::kPingGapMs, "actual sequential triggers keep quiet gap");
    std::cout << "PASS " << checks << " node runtime checks (host board adapter)\n";
}
