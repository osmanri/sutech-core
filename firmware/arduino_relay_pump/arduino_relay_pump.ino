/*
 * Su-Tech v2.1 Enterprise — Arduino Firmware for Multi-Sensor Irrigation Station
 * Competition Edition (RKNP / Republic Scientific Projects)
 * 
 * Hardware Layout:
 *   - D8:  5V Relay Module (KY-019) -> Controls 3-4.5V DC Pump
 *   - D9:  Buzzer Module (KY-012) -> Acoustic telemetry & alarms
 *   - D13: Onboard LED Indicator -> Active pump indicator
 *   - D7:  DHT11 Temperature & Humidity Sensor -> Field microclimate
 *   - A0:  Water Level Sensor -> Reservoir level & dry-run pump safety
 *   - A1:  Soil Moisture Sensor -> Root zone moisture feedback
 *
 * Communication Protocol (Serial 9600 baud):
 *   - PING              -> PONG
 *   - STATUS            -> OK:STATUS:PUMP=<0|1>:TIME_LEFT=<sec>:WATER_LVL=<0-100>:SOIL=<0-100>:TEMP=<degC>:HUM=<pct>
 *   - TELEMETRY         -> OK:TELEMETRY:PUMP=<0|1>:WATER=<lvl>:SOIL=<moist>:TEMP=<degC>:HUM=<pct>
 *   - MOISTURE          -> OK:MOISTURE=<soil>:WATER_LVL=<water>
 *   - WATER:<sec>       -> Turns pump ON for <sec> with dry-run safety check
 *   - WATER_FORCE:<sec> -> Turns pump ON for <sec> bypassing water level check
 *   - STOP              -> Immediate pump cutoff
 *   - BEEP              -> Test sound signal
 *
 * Pot scale (HX711 + load cell) for the evaporation experiment:
 *   - D2: HX711 DT, D3: HX711 SCK
 *   - SCALE             -> OK:SCALE=<grams>   (average of 5 readings; ERR:SCALE_NOT_READY if absent)
 *   - SCALE_RAW         -> OK:SCALE_RAW=<raw counts>
 *   - TARE              -> OK:TARE:OFFSET=<raw>   (current weight becomes 0 g, saved to EEPROM)
 *   - CALIBRATE:<grams> -> OK:CALIBRATE:FACTOR=<counts per gram>  (put a known mass, then send)
 *   - TELEMETRY additionally ends with :WEIGHT=<grams|NA>
 *
 * Flow meter (hall-effect, e.g. YF-S201 / YF-S401) for exact water doses:
 *   - A2: flow sensor signal (pin-change interrupt; D2/D3 stay with the HX711)
 *   - FLOW              -> OK:FLOW:PULSES=<total>:ML=<ml|NA>:PPML=<pulses per ml>
 *   - FLOW_RESET        -> OK:FLOW_RESET   (total counter back to 0)
 *   - FLOW_CAL:<ml>     -> OK:FLOW_CAL:PPML=<pulses per ml>
 *                          Run WATER:<sec> into a measuring cylinder first, read the ml, then send this.
 *   - WATER_ML:<ml>     -> OK:PUMP_ON:TARGET_ML=<ml>   (stops itself when the flow meter counts <ml>)
 *
 * Messages the Arduino sends on its own, without a command, start with "EVT:" so the
 * PC never mistakes them for the answer to its next command:
 *   - EVT:PUMP_OFF:REASON=<TIMER_COMPLETED|VOLUME_REACHED|TIMEOUT_BEFORE_VOLUME>:ML=<ml|NA>:PULSES=<n>
 * STOP answers synchronously: OK:PUMP_OFF:REASON=MANUAL_STOP:ML=<ml|NA>:PULSES=<n>
 */

#include <EEPROM.h>

#define RELAY_PIN 8
#define BUZZER_PIN 9
#define LED_INDICATOR 13
#define DHT_PIN 7
#define WATER_LEVEL_PIN A0
#define SOIL_MOISTURE_PIN A1
#define HX_DT_PIN 2
#define HX_SCK_PIN 3
#define FLOW_PIN A2  // PC2 = PCINT10 on the ATmega328P (Arduino Uno / Nano)

#define EEPROM_MAGIC_ADDR 0
#define EEPROM_OFFSET_ADDR 2
#define EEPROM_FACTOR_ADDR 6
#define EEPROM_MAGIC 0x5A
#define EEPROM_FLOW_MAGIC_ADDR 12
#define EEPROM_FLOW_FACTOR_ADDR 14
#define EEPROM_FLOW_MAGIC 0xA5

#define RELAY_ACTIVE HIGH
#define RELAY_INACTIVE LOW

#define MAX_PUMP_SECONDS 30.0f
#define MIN_WATER_LEVEL_PCT 8  // Threshold below which pump is blocked (dry-run protection)
#define MAX_DOSE_ML 1000.0f

bool pumpActive = false;
unsigned long pumpStartTime = 0;
unsigned long pumpDurationMs = 0;

// Flow meter: pulses counted in the pin-change interrupt
volatile unsigned long flowPulses = 0;
volatile uint8_t flowLastState = 0;
float flowPulsesPerMl = 0.0f;       // 0 = not calibrated
bool volumeMode = false;            // pump started by WATER_ML
unsigned long runStartPulses = 0;
unsigned long targetPulses = 0;
unsigned long lastRunPulses = 0;    // pulses of the last finished pump run (for FLOW_CAL)

ISR(PCINT1_vect) {
  uint8_t state = PINC & _BV(PC2);
  if (state && !flowLastState) flowPulses++;  // count rising edges only
  flowLastState = state;
}

unsigned long readFlowPulses() {
  noInterrupts();
  unsigned long p = flowPulses;
  interrupts();
  return p;
}

void loadFlowCalibration() {
  if (EEPROM.read(EEPROM_FLOW_MAGIC_ADDR) == EEPROM_FLOW_MAGIC) {
    EEPROM.get(EEPROM_FLOW_FACTOR_ADDR, flowPulsesPerMl);
  }
}

void saveFlowCalibration() {
  EEPROM.put(EEPROM_FLOW_FACTOR_ADDR, flowPulsesPerMl);
  EEPROM.write(EEPROM_FLOW_MAGIC_ADDR, EEPROM_FLOW_MAGIC);
}

void printMlOrNA(unsigned long pulses) {
  if (flowPulsesPerMl > 0.0f) {
    Serial.print((float)pulses / flowPulsesPerMl, 1);
  } else {
    Serial.print("NA");
  }
}

// Prototypes (the Arduino IDE adds these itself; explicit for other toolchains)
void startPump(float seconds, bool byVolume, unsigned long pulsesNeeded);
void stopPump(const char* reason, bool unsolicited);
void handleCommand(String cmd);
void playAlarm();

// Cached environmental sensor values
float cachedTemp = 24.0f;
float cachedHum = 50.0f;
unsigned long lastDHTReadTime = 0;

// Read water level from reservoir (0-100%)
int readWaterLevelPercent() {
  int raw = analogRead(WATER_LEVEL_PIN);
  // Typical resistive sensor: 0 in dry air, ~500-680 in water
  int pct = map(raw, 20, 650, 0, 100);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

// Read soil moisture (0-100%)
int readSoilMoisturePercent() {
  int raw = analogRead(SOIL_MOISTURE_PIN);
  int pct = map(raw, 20, 700, 0, 100);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

// Lightweight non-blocking/direct DHT11 bitbang reader (no external libraries needed)
bool readDHT11(float &temp, float &hum) {
  uint8_t data[5] = {0, 0, 0, 0, 0};

  pinMode(DHT_PIN, OUTPUT);
  digitalWrite(DHT_PIN, LOW);
  delay(18);
  digitalWrite(DHT_PIN, HIGH);
  delayMicroseconds(30);
  pinMode(DHT_PIN, INPUT_PULLUP);

  unsigned long timeout = micros();
  while (digitalRead(DHT_PIN) == HIGH) {
    if (micros() - timeout > 100) return false;
  }
  timeout = micros();
  while (digitalRead(DHT_PIN) == LOW) {
    if (micros() - timeout > 100) return false;
  }
  timeout = micros();
  while (digitalRead(DHT_PIN) == HIGH) {
    if (micros() - timeout > 100) return false;
  }

  for (int i = 0; i < 40; i++) {
    timeout = micros();
    while (digitalRead(DHT_PIN) == LOW) {
      if (micros() - timeout > 100) return false;
    }
    unsigned long t = micros();
    while (digitalRead(DHT_PIN) == HIGH) {
      if (micros() - timeout > 150) return false;
    }
    if ((micros() - t) > 40) {
      data[i / 8] |= (1 << (7 - (i % 8)));
    }
  }

  if (data[4] == ((data[0] + data[1] + data[2] + data[3]) & 0xFF)) {
    hum = (float)data[0] + (float)data[1] * 0.1f;
    temp = (float)data[2] + (float)data[3] * 0.1f;
    return true;
  }
  return false;
}

void updateDHTIfNeeded() {
  if (millis() - lastDHTReadTime > 2500) {
    float t, h;
    if (readDHT11(t, h)) {
      cachedTemp = t;
      cachedHum = h;
    }
    lastDHTReadTime = millis();
  }
}

// ---------------------------------------------------------------------------
// HX711 pot scale (bit-banged, no external library)
// ---------------------------------------------------------------------------
long scaleOffset = 0;
float scaleFactor = 0.0f;  // raw counts per gram; 0 = not calibrated

bool hxReady() {
  return digitalRead(HX_DT_PIN) == LOW;
}

// Returns false when the HX711 is not answering (not connected / not powered).
bool hxReadRaw(long &value) {
  unsigned long start = millis();
  while (!hxReady()) {
    if (millis() - start > 200) return false;
  }
  unsigned long data = 0;
  noInterrupts();
  for (uint8_t i = 0; i < 24; i++) {
    digitalWrite(HX_SCK_PIN, HIGH);
    delayMicroseconds(1);
    data = (data << 1) | (digitalRead(HX_DT_PIN) ? 1UL : 0UL);
    digitalWrite(HX_SCK_PIN, LOW);
    delayMicroseconds(1);
  }
  // 25th pulse selects channel A, gain 128 for the next conversion
  digitalWrite(HX_SCK_PIN, HIGH);
  delayMicroseconds(1);
  digitalWrite(HX_SCK_PIN, LOW);
  interrupts();
  if (data & 0x800000UL) data |= 0xFF000000UL;  // sign extend 24 -> 32 bit
  value = (long)data;
  return true;
}

// Average of n readings to suppress noise (the HX711 runs at 10 Hz).
bool hxReadAverage(uint8_t n, long &avg) {
  long long sum = 0;
  for (uint8_t i = 0; i < n; i++) {
    long v;
    if (!hxReadRaw(v)) return false;
    sum += v;
  }
  avg = (long)(sum / n);
  return true;
}

void loadScaleCalibration() {
  if (EEPROM.read(EEPROM_MAGIC_ADDR) == EEPROM_MAGIC) {
    EEPROM.get(EEPROM_OFFSET_ADDR, scaleOffset);
    EEPROM.get(EEPROM_FACTOR_ADDR, scaleFactor);
  }
}

void saveScaleCalibration() {
  EEPROM.put(EEPROM_OFFSET_ADDR, scaleOffset);
  EEPROM.put(EEPROM_FACTOR_ADDR, scaleFactor);
  EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC);
}

// Weight in grams; false if the scale is missing or not calibrated.
bool readWeightGrams(float &grams) {
  long raw;
  if (scaleFactor == 0.0f || !hxReadAverage(5, raw)) return false;
  grams = (float)(raw - scaleOffset) / scaleFactor;
  return true;
}

void printWeightOrNA() {
  float g;
  if (readWeightGrams(g)) {
    Serial.print(g, 1);
  } else {
    Serial.print("NA");
  }
}

void playChirp(int freq, int duration) {
  tone(BUZZER_PIN, freq, duration);
}

void playAlarm() {
  for (int i = 0; i < 3; i++) {
    tone(BUZZER_PIN, 450, 120);
    delay(150);
  }
}

void setup() {
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);

  pinMode(LED_INDICATOR, OUTPUT);
  digitalWrite(LED_INDICATOR, LOW);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(DHT_PIN, INPUT_PULLUP);
  pinMode(WATER_LEVEL_PIN, INPUT);
  pinMode(SOIL_MOISTURE_PIN, INPUT);

  pinMode(HX_DT_PIN, INPUT);
  pinMode(HX_SCK_PIN, OUTPUT);
  digitalWrite(HX_SCK_PIN, LOW);
  loadScaleCalibration();

  pinMode(FLOW_PIN, INPUT_PULLUP);
  flowLastState = PINC & _BV(PC2);
  PCMSK1 |= _BV(PCINT10);
  PCICR |= _BV(PCIE1);
  loadFlowCalibration();

  // Startup audio chirp
  playChirp(1200, 150);

  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for USB connection
  }

  Serial.println("INIT:SU-TECH:v2.1:MULTI_SENSOR_STATION_READY");
}

void loop() {
  // 1. Fail-safe pump cutoff timer
  if (pumpActive) {
    unsigned long elapsed = millis() - pumpStartTime;
    if (volumeMode && readFlowPulses() - runStartPulses >= targetPulses) {
      stopPump("VOLUME_REACHED", true);
    } else if (elapsed >= pumpDurationMs) {
      if (volumeMode) {
        playAlarm();  // the dose was not reached: empty tank, air in the hose or a blocked sensor
        stopPump("TIMEOUT_BEFORE_VOLUME", true);
      } else {
        stopPump("TIMER_COMPLETED", true);
      }
    }
  }

  // 2. Background environmental read
  updateDHTIfNeeded();

  // 3. Serial command processor
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0) {
      handleCommand(input);
    }
  }
}

void handleCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("PONG");
  }
  else if (cmd == "STATUS") {
    float timeLeft = 0.0f;
    if (pumpActive) {
      unsigned long elapsed = millis() - pumpStartTime;
      if (elapsed < pumpDurationMs) {
        timeLeft = (pumpDurationMs - elapsed) / 1000.0f;
      }
    }
    int waterLvl = readWaterLevelPercent();
    int soil = readSoilMoisturePercent();

    Serial.print("OK:STATUS:PUMP=");
    Serial.print(pumpActive ? "1" : "0");
    Serial.print(":TIME_LEFT=");
    Serial.print(timeLeft, 2);
    Serial.print(":WATER_LVL=");
    Serial.print(waterLvl);
    Serial.print(":SOIL=");
    Serial.print(soil);
    Serial.print(":TEMP=");
    Serial.print(cachedTemp, 1);
    Serial.print(":HUM=");
    Serial.println(cachedHum, 1);
  }
  else if (cmd == "TELEMETRY") {
    int waterLvl = readWaterLevelPercent();
    int soil = readSoilMoisturePercent();
    Serial.print("OK:TELEMETRY:PUMP=");
    Serial.print(pumpActive ? "1" : "0");
    Serial.print(":WATER=");
    Serial.print(waterLvl);
    Serial.print(":SOIL=");
    Serial.print(soil);
    Serial.print(":TEMP=");
    Serial.print(cachedTemp, 1);
    Serial.print(":HUM=");
    Serial.print(cachedHum, 1);
    Serial.print(":WEIGHT=");
    printWeightOrNA();
    Serial.println();
  }
  else if (cmd == "SCALE") {
    float g;
    if (readWeightGrams(g)) {
      Serial.print("OK:SCALE=");
      Serial.println(g, 1);
    } else {
      Serial.println("ERR:SCALE_NOT_READY");
    }
  }
  else if (cmd == "SCALE_RAW") {
    long raw;
    if (hxReadAverage(5, raw)) {
      Serial.print("OK:SCALE_RAW=");
      Serial.println(raw);
    } else {
      Serial.println("ERR:SCALE_NOT_READY");
    }
  }
  else if (cmd == "TARE") {
    long raw;
    if (!hxReadAverage(10, raw)) {
      Serial.println("ERR:SCALE_NOT_READY");
      return;
    }
    scaleOffset = raw;
    saveScaleCalibration();
    Serial.print("OK:TARE:OFFSET=");
    Serial.println(scaleOffset);
  }
  else if (cmd.startsWith("CALIBRATE:")) {
    float grams = cmd.substring(10).toFloat();
    long raw;
    if (grams <= 0.0f) {
      Serial.println("ERR:INVALID_MASS");
      return;
    }
    if (!hxReadAverage(10, raw)) {
      Serial.println("ERR:SCALE_NOT_READY");
      return;
    }
    if (raw == scaleOffset) {
      Serial.println("ERR:NO_LOAD_DETECTED");
      return;
    }
    scaleFactor = (float)(raw - scaleOffset) / grams;
    saveScaleCalibration();
    Serial.print("OK:CALIBRATE:FACTOR=");
    Serial.println(scaleFactor, 3);
  }
  else if (cmd == "MOISTURE") {
    int soil = readSoilMoisturePercent();
    Serial.print("OK:MOISTURE=");
    Serial.println(soil);
  }
  else if (cmd == "WATER_LEVEL") {
    int waterLvl = readWaterLevelPercent();
    Serial.print("OK:WATER_LEVEL=");
    Serial.println(waterLvl);
  }
  else if (cmd == "BEEP") {
    playChirp(1500, 200);
    Serial.println("OK:BEEP");
  }
  else if (cmd.startsWith("WATER:")) {
    String secStr = cmd.substring(6);
    float seconds = secStr.toFloat();
    if (seconds <= 0.0f) {
      Serial.println("ERR:INVALID_DURATION");
      return;
    }
    if (seconds > MAX_PUMP_SECONDS) {
      seconds = MAX_PUMP_SECONDS;
    }

    // Safety: check water level in reservoir
    int waterLvl = readWaterLevelPercent();
    // If water sensor is reading < threshold, block pump
    if (waterLvl < MIN_WATER_LEVEL_PCT) {
      playAlarm();
      Serial.print("ERR:WATER_EMPTY:LEVEL=");
      Serial.println(waterLvl);
      return;
    }

    startPump(seconds, false, 0);
    Serial.print("OK:PUMP_ON:DURATION=");
    Serial.println(seconds, 2);
  }
  else if (cmd.startsWith("WATER_FORCE:")) {
    String secStr = cmd.substring(12);
    float seconds = secStr.toFloat();
    if (seconds <= 0.0f) {
      Serial.println("ERR:INVALID_DURATION");
      return;
    }
    if (seconds > MAX_PUMP_SECONDS) {
      seconds = MAX_PUMP_SECONDS;
    }
    startPump(seconds, false, 0);
    Serial.print("OK:PUMP_ON:DURATION=");
    Serial.println(seconds, 2);
  }
  else if (cmd == "STOP") {
    stopPump("MANUAL_STOP", false);
  }
  else if (cmd == "FLOW") {
    unsigned long p = readFlowPulses();
    Serial.print("OK:FLOW:PULSES=");
    Serial.print(p);
    Serial.print(":ML=");
    printMlOrNA(p);
    Serial.print(":PPML=");
    Serial.println(flowPulsesPerMl, 4);
  }
  else if (cmd == "FLOW_RESET") {
    noInterrupts();
    flowPulses = 0;
    interrupts();
    Serial.println("OK:FLOW_RESET");
  }
  else if (cmd.startsWith("FLOW_CAL:")) {
    float ml = cmd.substring(9).toFloat();
    if (ml <= 0.0f) {
      Serial.println("ERR:INVALID_VOLUME");
      return;
    }
    if (pumpActive) {
      Serial.println("ERR:PUMP_RUNNING");
      return;
    }
    if (lastRunPulses == 0) {
      Serial.println("ERR:NO_FLOW_PULSES");
      return;
    }
    flowPulsesPerMl = (float)lastRunPulses / ml;
    saveFlowCalibration();
    Serial.print("OK:FLOW_CAL:PPML=");
    Serial.println(flowPulsesPerMl, 4);
  }
  else if (cmd.startsWith("WATER_ML:")) {
    float ml = cmd.substring(9).toFloat();
    if (ml <= 0.0f || ml > MAX_DOSE_ML) {
      Serial.println("ERR:INVALID_VOLUME");
      return;
    }
    if (flowPulsesPerMl <= 0.0f) {
      Serial.println("ERR:FLOW_NOT_CALIBRATED");
      return;
    }
    if (pumpActive) {
      Serial.println("ERR:PUMP_RUNNING");
      return;
    }
    int waterLvl = readWaterLevelPercent();
    if (waterLvl < MIN_WATER_LEVEL_PCT) {
      playAlarm();
      Serial.print("ERR:WATER_EMPTY:LEVEL=");
      Serial.println(waterLvl);
      return;
    }
    unsigned long target = (unsigned long)(ml * flowPulsesPerMl + 0.5f);
    if (target == 0) target = 1;
    startPump(MAX_PUMP_SECONDS, true, target);
    Serial.print("OK:PUMP_ON:TARGET_ML=");
    Serial.println(ml, 1);
  }
  else {
    Serial.println("ERR:UNKNOWN_COMMAND");
  }
}

// The caller prints the OK:PUMP_ON reply.
void startPump(float seconds, bool byVolume, unsigned long pulsesNeeded) {
  pumpDurationMs = (unsigned long)(seconds * 1000.0f);
  volumeMode = byVolume;
  targetPulses = pulsesNeeded;
  runStartPulses = readFlowPulses();
  pumpStartTime = millis();
  pumpActive = true;

  digitalWrite(RELAY_PIN, RELAY_ACTIVE);
  digitalWrite(LED_INDICATOR, HIGH);
  playChirp(1400, 120);
}

// unsolicited = true when the Arduino stops the pump by itself (timer / volume):
// the line then starts with EVT: instead of OK: so it is never read as a command reply.
void stopPump(const char* reason, bool unsolicited) {
  bool wasActive = pumpActive;
  pumpActive = false;
  volumeMode = false;
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  digitalWrite(LED_INDICATOR, LOW);
  if (wasActive) {
    lastRunPulses = readFlowPulses() - runStartPulses;
  }
  playChirp(900, 180);

  Serial.print(unsolicited ? "EVT:PUMP_OFF:REASON=" : "OK:PUMP_OFF:REASON=");
  Serial.print(reason);
  Serial.print(":ML=");
  printMlOrNA(wasActive ? lastRunPulses : 0);
  Serial.print(":PULSES=");
  Serial.println(wasActive ? lastRunPulses : 0);
}
