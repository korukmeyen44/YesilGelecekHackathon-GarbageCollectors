#include <cstdlib>
#include <iostream>
#include <string>
#include <fstream>
#include <iterator>
#include "http_receipt.h"

unsigned checks = 0;
void expect(bool ok, const char* name) {
    ++checks;
    if (!ok) { std::cerr << "FAIL delivery: " << name << '\n'; std::exit(1); }
}
int main(int argc, char** argv) {
    gc::Packet p; p.nodeId=1; p.bootId=42; p.sequence=7;
    gc::ReplayGuard guard;
    expect(guard.accept(p), "first packet accepted");
    expect(!guard.accept(p), "retry cannot refresh measurement age");
    p.sequence=6; expect(!guard.accept(p), "old sequence rejected");
    p.sequence=8; expect(guard.accept(p), "new sequence accepted");
    p.bootId=43; p.sequence=1; expect(guard.accept(p), "reboot advances identity");
    p.bootId=42; p.sequence=100; expect(!guard.accept(p), "previous boot rejected");
    p.nodeId=2; expect(guard.accept(p), "nodes have independent identity state");
    p.nodeId=0; expect(!guard.accept(p), "zero node rejected");
    expect(!gc::expired(29999,0) && gc::expired(30001,0), "freshness boundary");
    expect(gc::expired(31000,0xFFFFFC18UL), "expiry across millis wrap");
    expect(gc::retryableHttp(-1) && gc::retryableHttp(408) && gc::retryableHttp(429) && gc::retryableHttp(503), "temporary failures retried");
    expect(!gc::retryableHttp(401) && !gc::retryableHttp(409) && !gc::retryableHttp(302), "permanent errors not retried");
    expect(!gc::storedHttp(202) && !gc::storedHttp(204), "non-durable 2xx rejected");
    for (uint8_t i=0;i<100;++i) {
        expect(gc::reconnectDelay(i,500)>=10000 && gc::reconnectDelay(i,500)<=30500, "bounded association backoff");
    }
    const char* url="http://192.168.1.20:8080/api/telemetry";
    expect(gc::validGatewayConfig("WiFi","password123",url,"token",""), "valid LAN configuration");
    expect(!gc::validGatewayConfig("YOUR_2_4_GHZ_WIFI","password123",url,"",""), "placeholder SSID rejected");
    expect(!gc::validGatewayConfig("WiFi","YOUR_WIFI_PASSWORD",url,"",""), "placeholder password rejected");
    expect(!gc::validGatewayConfig("WiFi","password123","http://localhost:8080/api/telemetry","",""), "gateway loopback rejected");
    expect(!gc::validGatewayConfig("WiFi","password123","http://192.168.1.20:8080/","",""), "wrong API path rejected");
    expect(!gc::validGatewayConfig("WiFi","password123","https://example.org/api/telemetry","",""), "TLS cannot disable CA validation");
    expect(gc::validGatewayConfig("WiFi","password123","https://example.org/api/telemetry","token","CA"), "TLS configuration requires CA");
    expect(!gc::validGatewayConfig("WiFi","password123",url,"a\r\nb",""), "header injection rejected");
    p.nodeId=1; p.bootId=42; p.sequence=7;
    const std::string receipt="{\"inserted\":true,\"duplicate\":false,\"measurement_id\":{\"node_id\":1,\"boot_id\":42,\"sequence\":7}}";
    expect(gc::validReceipt(receipt.c_str(),receipt.size(),201,p), "durable receipt accepted");
    expect(!gc::validReceipt(receipt.c_str(),receipt.size(),200,p), "status and receipt must agree");
    p.sequence=8;
    expect(!gc::validReceipt(receipt.c_str(),receipt.size(),201,p), "another measurement receipt rejected");
    p.sequence=7;
    const std::string duplicate="{\"inserted\":false,\"duplicate\":true,\"measurement_id\":{\"node_id\":1,\"boot_id\":42,\"sequence\":7}}";
    expect(gc::validReceipt(duplicate.c_str(),duplicate.size(),200,p), "idempotent duplicate receipt accepted");
    const char* invalid[]={"{}","not JSON","{\"ok\":true}","{\"inserted\":true,\"duplicate\":false,\"measurement_id\":{\"node_id\":\"1\",\"boot_id\":42,\"sequence\":7}}"};
    for(const char* value:invalid) expect(!gc::validReceipt(value,strlen(value),201,p), "malformed or unbound response rejected");
    expect(!gc::validReceipt(receipt.c_str(),0,201,p), "empty receipt rejected");
    std::string large(1025,'x'); expect(!gc::validReceipt(large.c_str(),large.size(),201,p), "oversized receipt rejected");
    if (argc == 3) {
        std::ifstream file(argv[1]);
        std::string external((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
        p.nodeId=1; p.bootId=0x12345678UL; p.sequence=0x01020304UL;
        expect(gc::validReceipt(external.c_str(),external.size(),std::atoi(argv[2]),p), "real application HTTP receipt accepted by production C++ parser");
    }
    std::cout << "PASS " << checks << " gateway delivery checks\n";
}
