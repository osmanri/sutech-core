// Minimal Arduino stand-in so the firmware logic can be compiled and tested on a PC.
// Only what arduino_relay_pump.ino uses. Not a hardware simulator: sensors return fixed values.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <deque>

#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define A0 14
#define A1 15
#define A2 16
#define PC2 2
#define PCINT10 2
#define PCIE1 1
#define _BV(b) (1u << (b))
#define ISR(vector) void vector()

extern uint8_t PINC, PCMSK1, PCICR;
extern unsigned long fake_millis, fake_micros;
extern int fake_analog[3];

inline unsigned long millis() { return fake_millis; }
inline unsigned long micros() { return fake_micros += 10; }
inline void delay(unsigned long ms) { fake_millis += ms; }
inline void delayMicroseconds(unsigned int) {}
inline void noInterrupts() {}
inline void interrupts() {}
inline void pinMode(int, int) {}
inline void digitalWrite(int, int) {}
inline int digitalRead(int) { return LOW; }
inline int analogRead(int pin) { return fake_analog[pin - A0]; }
inline void tone(int, unsigned int, unsigned long) {}
inline long map(long x, long a, long b, long c, long d) { return (x - a) * (d - c) / (b - a) + c; }

class String {
 public:
  std::string s;
  String() {}
  String(const char* c) : s(c) {}
  String(const std::string& c) : s(c) {}
  void trim() {
    size_t a = s.find_first_not_of(" \r\n\t"), b = s.find_last_not_of(" \r\n\t");
    s = (a == std::string::npos) ? "" : s.substr(a, b - a + 1);
  }
  unsigned int length() const { return s.size(); }
  bool startsWith(const char* p) const { return s.rfind(p, 0) == 0; }
  String substring(unsigned int from) const { return from >= s.size() ? String() : String(s.substr(from)); }
  float toFloat() const { return (float)atof(s.c_str()); }
  bool operator==(const char* o) const { return s == o; }
};

class FakeSerial {
 public:
  std::deque<std::string> in;
  std::string out;
  void begin(long) {}
  explicit operator bool() const { return true; }
  int available() { return in.empty() ? 0 : 1; }
  String readStringUntil(char) { std::string l = in.front(); in.pop_front(); return String(l); }
  void print(const char* v) { out += v; }
  void print(const String& v) { out += v.s; }
  void print(int v) { out += std::to_string(v); }
  void print(long v) { out += std::to_string(v); }
  void print(unsigned long v) { out += std::to_string(v); }
  void print(double v, int digits = 2) { char b[64]; snprintf(b, sizeof b, "%.*f", digits, v); out += b; }
  template <typename T> void println(T v) { print(v); out += "\n"; }
  void println(double v, int digits) { print(v, digits); out += "\n"; }
  void println() { out += "\n"; }
};
extern FakeSerial Serial;

class FakeEEPROM {
 public:
  uint8_t mem[1024];
  FakeEEPROM() { memset(mem, 0xFF, sizeof mem); }
  uint8_t read(int a) { return mem[a]; }
  void write(int a, uint8_t v) { mem[a] = v; }
  template <typename T> void get(int a, T& v) { memcpy(&v, mem + a, sizeof v); }
  template <typename T> void put(int a, const T& v) { memcpy(mem + a, &v, sizeof v); }
};
extern FakeEEPROM EEPROM;
