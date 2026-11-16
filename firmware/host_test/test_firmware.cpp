// Host test of the pump / flow-meter logic in arduino_relay_pump.ino.
// Build and run: g++ -std=c++17 -I. test_firmware.cpp -o t && ./t
#include "Arduino.h"
uint8_t PINC = 0, PCMSK1 = 0, PCICR = 0;
unsigned long fake_millis = 0, fake_micros = 0;
int fake_analog[3] = {400, 300, 0};  // water level ~60 %, soil ~41 %
FakeSerial Serial;
FakeEEPROM EEPROM;
#include "../arduino_relay_pump/arduino_relay_pump.ino"

static int failures = 0;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL line %d: %s\n", __LINE__, #cond); failures++; } } while (0)

static std::string cmd(const char* c) {
  Serial.out.clear();
  Serial.in.push_back(c);
  loop();
  return Serial.out;
}
static void pulses(int n) {  // n rising edges on A2
  for (int i = 0; i < n; i++) { PINC |= _BV(PC2); PCINT1_vect(); PINC &= ~_BV(PC2); PCINT1_vect(); }
}
static std::string tick(unsigned long ms) {  // let time pass, collect unsolicited output
  Serial.out.clear();
  fake_millis += ms;
  loop();
  return Serial.out;
}
static bool has(const std::string& out, const char* s) { return out.find(s) != std::string::npos; }

int main() {
  setup();
  CHECK(PCICR & _BV(PCIE1));
  CHECK(PCMSK1 & _BV(PCINT10));

  // Before calibration a volume dose is refused and FLOW reports NA.
  CHECK(has(cmd("WATER_ML:50"), "ERR:FLOW_NOT_CALIBRATED"));
  CHECK(has(cmd("FLOW"), "OK:FLOW:PULSES=0:ML=NA"));
  CHECK(has(cmd("FLOW_CAL:100"), "ERR:NO_FLOW_PULSES"));

  // Timed run into a measuring cylinder: 225 pulses, the cylinder shows 100 ml.
  CHECK(has(cmd("WATER:10"), "OK:PUMP_ON:DURATION=10.00"));
  pulses(225);
  std::string ev = tick(10001);
  CHECK(has(ev, "EVT:PUMP_OFF:REASON=TIMER_COMPLETED:ML=NA:PULSES=225"));
  CHECK(!has(ev, "OK:PUMP_OFF"));  // unsolicited lines never look like a reply
  CHECK(!pumpActive);
  CHECK(has(cmd("FLOW_CAL:100"), "OK:FLOW_CAL:PPML=2.2500"));
  CHECK(EEPROM.read(EEPROM_FLOW_MAGIC_ADDR) == EEPROM_FLOW_MAGIC);

  // Volume dose stops itself when the counted pulses reach the target.
  CHECK(has(cmd("WATER_ML:40"), "OK:PUMP_ON:TARGET_ML=40.0"));
  CHECK(pumpActive);
  pulses(89);                         // 89 < 90 = 40 ml * 2.25
  CHECK(tick(500).empty());
  CHECK(pumpActive);
  pulses(1);
  ev = tick(10);
  CHECK(has(ev, "EVT:PUMP_OFF:REASON=VOLUME_REACHED:ML=40.0:PULSES=90"));
  CHECK(!pumpActive);

  // No flow (empty hose): the 30 s cap stops the pump and says the dose was not reached.
  cmd("WATER_ML:40");
  pulses(10);
  ev = tick(30001);
  CHECK(has(ev, "EVT:PUMP_OFF:REASON=TIMEOUT_BEFORE_VOLUME:ML=4.4:PULSES=10"));
  CHECK(!pumpActive);

  // Manual STOP answers synchronously with OK:.
  cmd("WATER:5");
  pulses(45);
  CHECK(has(cmd("STOP"), "OK:PUMP_OFF:REASON=MANUAL_STOP:ML=20.0:PULSES=45"));

  // Bad input and dry-run protection.
  CHECK(has(cmd("WATER_ML:0"), "ERR:INVALID_VOLUME"));
  CHECK(has(cmd("WATER_ML:5000"), "ERR:INVALID_VOLUME"));
  fake_analog[0] = 10;  // reservoir empty
  CHECK(has(cmd("WATER_ML:40"), "ERR:WATER_EMPTY"));
  CHECK(!pumpActive);
  fake_analog[0] = 400;

  // Total counter and reset.
  CHECK(has(cmd("FLOW"), "OK:FLOW:PULSES=370:ML=164.4:PPML=2.2500"));
  CHECK(has(cmd("FLOW_RESET"), "OK:FLOW_RESET"));
  CHECK(has(cmd("FLOW"), "OK:FLOW:PULSES=0:ML=0.0"));

  // Calibration survives a reboot (EEPROM).
  flowPulsesPerMl = 0.0f;
  loadFlowCalibration();
  CHECK(flowPulsesPerMl > 2.24f && flowPulsesPerMl < 2.26f);

  if (failures == 0) printf("firmware host test: all checks passed\n");
  return failures == 0 ? 0 : 1;
}
