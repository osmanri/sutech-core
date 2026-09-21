/*
 * Su-Tech v2.0 Enterprise — Arduino Firmware for Relay & Water Pump
 * Hardware: Arduino Uno / Nano + 5V Relay Module (KY-019) + 3-4.5V DC Pump
 * 
 * Communication Protocol (Serial 9600 baud):
 *   Commands from Python Bot:
 *     - PING              -> returns PONG
 *     - STATUS            -> returns OK:STATUS:PUMP=<0|1>:TIME_LEFT=<sec>
 *     - WATER:<seconds>   -> activates pump for <seconds> (max 30.0s fail-safe)
 *     - STOP              -> immediately cuts off pump
 *
 * Fail-Safe Protections:
 *   1. Hardware Watchdog: pump automatically turns off after MAX_PUMP_SECONDS (30s)
 *      even if host loses connection or hangs.
 *   2. Boot Safety: relay pin is pulled inactive immediately on reset.
 *   3. Non-blocking millis() timer prevents blocking the serial loop.
 */

#define RELAY_PIN 8
#define BUZZER_PIN 9
#define LED_INDICATOR 13
#define SOIL_MOISTURE_PIN A0

// Some relay boards trigger on HIGH, others on LOW.
// Standard KY-019 triggers on HIGH. Adjust if your module is active-low.
#define RELAY_ACTIVE HIGH
#define RELAY_INACTIVE LOW

#define MAX_PUMP_SECONDS 30.0f

bool pumpActive = false;
unsigned long pumpStartTime = 0;
unsigned long pumpDurationMs = 0;

int readMoisturePercent() {
  int raw = analogRead(SOIL_MOISTURE_PIN);
  // Map typical sensor range (0 - 800) to percentage (0 - 100%)
  int pct = map(raw, 0, 750, 0, 100);
  if (pct < 0) pct = 0;
  if (pct > 100) pct = 100;
  return pct;
}

void setup() {
  // Ensure relay is safely turned off BEFORE setting pin as output
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);

  pinMode(LED_INDICATOR, OUTPUT);
  digitalWrite(LED_INDICATOR, LOW);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(SOIL_MOISTURE_PIN, INPUT);

  Serial.begin(9600);
  while (!Serial) {
    ; // Wait for serial port to connect (needed for native USB)
  }
  
  // Announce startup
  Serial.println("INIT:SU-TECH:v2.0:READY");
}

void loop() {
  // 1. Check fail-safe pump timer
  if (pumpActive) {
    unsigned long elapsed = millis() - pumpStartTime;
    if (elapsed >= pumpDurationMs) {
      stopPump("TIMER_COMPLETED");
    }
  }

  // 2. Read commands from Serial port
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
    int moisture = readMoisturePercent();
    Serial.print("OK:STATUS:PUMP=");
    Serial.print(pumpActive ? "1" : "0");
    Serial.print(":TIME_LEFT=");
    Serial.print(timeLeft, 2);
    Serial.print(":MOISTURE=");
    Serial.println(moisture);
  }
  else if (cmd == "MOISTURE") {
    int moisture = readMoisturePercent();
    Serial.print("OK:MOISTURE=");
    Serial.println(moisture);
  }
  else if (cmd.startsWith("WATER:")) {
    String secStr = cmd.substring(6);
    float seconds = secStr.toFloat();
    if (seconds <= 0.0f) {
      Serial.println("ERR:INVALID_DURATION");
      return;
    }
    // Hard fail-safe cap: never allow continuous pumping longer than 30s
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
  tone(BUZZER_PIN, 1200, 100);

  Serial.print("OK:PUMP_ON:DURATION=");
  Serial.println(seconds, 2);
}

void stopPump(const char* reason) {
  pumpActive = false;
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  digitalWrite(LED_INDICATOR, LOW);
  tone(BUZZER_PIN, 800, 150);

  Serial.print("OK:PUMP_OFF:REASON=");
  Serial.println(reason);
}

