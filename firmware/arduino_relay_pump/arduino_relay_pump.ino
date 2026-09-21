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
#define LED_INDICATOR 13

// Some relay boards trigger on HIGH, others on LOW.
// Standard KY-019 triggers on HIGH. Adjust if your module is active-low.
#define RELAY_ACTIVE HIGH
#define RELAY_INACTIVE LOW

#define MAX_PUMP_SECONDS 30.0f

bool pumpActive = false;
unsigned long pumpStartTime = 0;
unsigned long pumpDurationMs = 0;

void setup() {
  // Ensure relay is safely turned off BEFORE setting pin as output
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);

  pinMode(LED_INDICATOR, OUTPUT);
  digitalWrite(LED_INDICATOR, LOW);

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
    Serial.print("OK:STATUS:PUMP=");
    Serial.print(pumpActive ? "1" : "0");
    Serial.print(":TIME_LEFT=");
    Serial.println(timeLeft, 2);
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

  Serial.print("OK:PUMP_ON:DURATION=");
  Serial.println(seconds, 2);
}

void stopPump(const char* reason) {
  pumpActive = false;
  digitalWrite(RELAY_PIN, RELAY_INACTIVE);
  digitalWrite(LED_INDICATOR, LOW);

  Serial.print("OK:PUMP_OFF:REASON=");
  Serial.println(reason);
}
