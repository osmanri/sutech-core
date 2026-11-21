// Host test of the pump / flow-meter logic in arduino_relay_pump.ino.
// Build and run: g++ -std=c++17 -I. test_firmware.cpp -o t && ./t
#include "Arduino.h"
#include <limits>
uint8_t PINC = 0, PCMSK1 = 0, PCICR = 0;
unsigned long fake_millis = 0, fake_micros = 0;
int fake_analog[3] = {400, 300, 0};  // water level ~60 %, soil ~41 %
int fake_output[20] = {};
unsigned long fake_output_changed_at[20] = {};
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
  fake_output[RELAY_PIN] = RELAY_ACTIVE;
  setup();
  CHECK(PCICR & _BV(PCIE1));
  CHECK(PCMSK1 & _BV(PCINT10));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);

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
  CHECK(fake_output[RELAY_PIN] == RELAY_ACTIVE);
  pulses(89);                         // 89 < 90 = 40 ml * 2.25
  CHECK(tick(500).empty());
  CHECK(fake_output[RELAY_PIN] == RELAY_ACTIVE);
  CHECK(has(cmd("FLOW_RESET"), "ERR:PUMP_RUNNING"));
  CHECK(has(cmd("FLOW_CAL:100"), "ERR:PUMP_RUNNING"));
  pulses(1);
  ev = tick(10);
  CHECK(has(ev, "EVT:PUMP_OFF:REASON=VOLUME_REACHED:ML=40.0:PULSES=90"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);

  // Lost flow after 10 pulses: the 30 s cap cuts the relay before the alarm delay.
  cmd("WATER_ML:40");
  const unsigned long deadline = fake_millis + 30000;
  pulses(10);
  CHECK(tick(29000).empty());
  CHECK(fake_output[RELAY_PIN] == RELAY_ACTIVE);
  ev = tick(deadline - fake_millis);
  CHECK(has(ev, "EVT:PUMP_OFF:REASON=TIMEOUT_BEFORE_VOLUME:ML=4.4:PULSES=10"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  CHECK(fake_output_changed_at[RELAY_PIN] == deadline);
  CHECK(has(cmd("FLOW_CAL:1"), "ERR:NO_FLOW_PULSES"));

  // Manual STOP answers synchronously and cuts the relay in both modes.
  cmd("WATER:5");
  pulses(45);
  CHECK(has(cmd("STOP"), "OK:PUMP_OFF:REASON=MANUAL_STOP:ML=20.0:PULSES=45"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  cmd("WATER_ML:40");
  CHECK(has(cmd("STOP"), "OK:PUMP_OFF:REASON=MANUAL_STOP:ML=0.0:PULSES=0"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  CHECK(tick(30000).empty());

  // Bad input and dry-run protection.
  CHECK(has(cmd("WATER_ML:0"), "ERR:INVALID_VOLUME"));
  CHECK(has(cmd("WATER_ML:5000"), "ERR:INVALID_VOLUME"));
  fake_analog[0] = 10;  // reservoir empty
  CHECK(has(cmd("WATER_ML:40"), "ERR:WATER_EMPTY"));
  CHECK(has(cmd("WATER:10"), "ERR:WATER_EMPTY"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  CHECK(has(cmd("WATER_FORCE:60"), "OK:PUMP_ON:DURATION=30.00"));
  CHECK(has(cmd("STOP"), "OK:PUMP_OFF:REASON=MANUAL_STOP"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  fake_analog[0] = 400;

  // Total counter and reset.
  CHECK(has(cmd("FLOW"), "OK:FLOW:PULSES=370:ML=164.4:PPML=2.2500"));
  CHECK(has(cmd("FLOW_RESET"), "OK:FLOW_RESET"));
  CHECK(has(cmd("FLOW"), "OK:FLOW:PULSES=0:ML=0.0"));

  // Calibration survives a reboot (EEPROM).
  flowPulsesPerMl = 0.0f;
  loadFlowCalibration();
  CHECK(flowPulsesPerMl > 2.24f && flowPulsesPerMl < 2.26f);

  // A second start cannot extend the timed cutoff or replace a volume run.
  CHECK(has(cmd("WATER:300"), "OK:PUMP_ON:DURATION=30.00"));
  CHECK(tick(29000).empty());
  CHECK(has(cmd("WATER:30"), "ERR:PUMP_RUNNING"));
  CHECK(has(cmd("WATER_FORCE:30"), "ERR:PUMP_RUNNING"));
  CHECK(has(tick(1000), "EVT:PUMP_OFF:REASON=TIMER_COMPLETED"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  CHECK(has(cmd("WATER_ML:1000"), "OK:PUMP_ON:TARGET_ML=1000.0"));
  CHECK(has(cmd("WATER:5"), "ERR:PUMP_RUNNING"));
  CHECK(has(cmd("WATER_FORCE:5"), "ERR:PUMP_RUNNING"));
  CHECK(has(tick(30000), "EVT:PUMP_OFF:REASON=TIMEOUT_BEFORE_VOLUME:ML=0.0:PULSES=0"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  CHECK(has(cmd("WATER_ML:1000.1"), "ERR:INVALID_VOLUME"));

  // Invalid serial numbers and corrupt EEPROM must not energize the relay.
  CHECK(has(cmd("WATER:nan"), "ERR:INVALID_DURATION"));
  CHECK(has(cmd("WATER_FORCE:inf"), "ERR:INVALID_DURATION"));
  CHECK(has(cmd("WATER_ML:40ml"), "ERR:INVALID_VOLUME"));
  CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  cmd("WATER:1");
  pulses(225);
  CHECK(has(tick(1000), "EVT:PUMP_OFF:REASON=TIMER_COMPLETED"));
  for (const char* bad : {"FLOW_CAL:0", "FLOW_CAL:-1", "FLOW_CAL:nan", "FLOW_CAL:inf", "FLOW_CAL:5ml"}) {
    CHECK(has(cmd(bad), "ERR:INVALID_VOLUME"));
  }
  CHECK(has(cmd("FLOW_CAL:1e-10"), "ERR:INVALID_FLOW_CALIBRATION"));
  CHECK(has(cmd("FLOW"), "PPML=2.2500"));
  for (float bad : {0.0f, -2.25f, std::numeric_limits<float>::quiet_NaN(),
                    std::numeric_limits<float>::infinity(), 1.0e10f}) {
    EEPROM.put(EEPROM_FLOW_FACTOR_ADDR, bad);
    loadFlowCalibration();
    CHECK(has(cmd("WATER_ML:40"), "ERR:FLOW_NOT_CALIBRATED"));
    CHECK(fake_output[RELAY_PIN] == RELAY_INACTIVE);
  }

  if (failures == 0) printf("firmware host test: all checks passed\n");
  return failures == 0 ? 0 : 1;
}
