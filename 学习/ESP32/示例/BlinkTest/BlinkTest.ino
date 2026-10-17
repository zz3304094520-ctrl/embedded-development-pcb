/*
 * ESP32-S3 Blink Test
 * Built-in LED: GPIO 48 (most ESP32-S3 DevKit boards)
 * If your board uses a different pin, change LED_BUILTIN below
 */

#define LED_BUILTIN 48

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("ESP32-S3 Blink Test Starting...");
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  Serial.println("LED ON");
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  Serial.println("LED OFF");
  delay(1000);
}
