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
 */

#define RELAY_PIN 8
#define BUZZER_PIN 9
#define LED_INDICATOR 13
#define DHT_PIN 7
#define WATER_LEVEL_PIN A0
#define SOIL_MOISTURE_PIN A1

#define RELAY_ACTIVE HIGH
#define RELAY_INACTIVE LOW

#define MAX_PUMP_SECONDS 30.0f
#define MIN_WATER_LEVEL_PCT 8  // Threshold below which pump is blocked (dry-run protection)

bool pumpActive = false;
unsigned long pumpStartTime = 0;
unsigned long pumpDurationMs = 0;

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
    if (elapsed >= pumpDurationMs) {
      stopPump("TIMER_COMPLETED");
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
    Serial.println(cachedHum, 1);
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

    startPump(seconds);
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
    startPump(seconds);
  }
  else if (cmd == "STOP") {
    stopPump("MANUAL_STOP");
  }
  else {
    Serial.println("ERR:UNKNOWN_COMMAND");
  }
}

void startPump(float seconds) {
  pumpDurationMs = (unsigned long)(seconds * 1000.0f);
  pumpStartTime = millis();
  pumpActive = true;

  digitalWrite(RELAY_PIN, RELAY_ACTIVE);
  digitalWrite(LED_INDICATOR, HIGH);
  playChirp(1400, 120);

  Serial.print("OK:PUMP_ON:DURATION=");
  Serial.println(seconds, 2);
}

void stopPump(const char* reason) {
  pumpActive = false;
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  digitalWrite(LED_INDICATOR, LOW);
  playChirp(900, 180);

  Serial.print("OK:PUMP_OFF:REASON=");
  Serial.println(reason);
}
