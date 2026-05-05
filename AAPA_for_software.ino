/**
 * FYSETC E4 v1.3 - WiFi AP + Web Interface con Gradi (+1, +10, +90...)
 * * --- ISTRUZIONI WIFI ---
 * Nome Rete: APA
 * Password:  Apa1234
 * Indirizzo: 192.168.4.1
 */

#include <Arduino.h>
#include <TMCStepper.h>
#include <AccelStepper.h>
#include <WiFi.h>
#include <WebServer.h>

#define ENABLE_PIN 25

// --- INDIRIZZI TMC2209 ---
#define X_ADDR      1
#define Y_ADDR      3

// --- PINOUT ---
#define X_STEP_PIN 27
#define X_DIR_PIN  26
#define Y_STEP_PIN 33
#define Y_DIR_PIN  32

// --- UART ---
#define SERIAL_PORT Serial1
#define DRIVER_UART_RX 15
#define DRIVER_UART_TX 15
#define R_SENSE 0.11f

// --- OGGETTI ---
TMC2209Stepper driverX(&SERIAL_PORT, R_SENSE, X_ADDR);
TMC2209Stepper driverY(&SERIAL_PORT, R_SENSE, Y_ADDR);

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);

// --- WIFI ---
const char* ssid = "APA";
const char* password = "Apa1234";

WebServer server(80);
WiFiServer telnetServer(23);
WiFiClient telnetClient;

// --- STATO ---
int x_run_ma = 600;
float x_hold_mult = 0.5;
int x_microsteps = 16;

int y_run_ma = 600;
float y_hold_mult = 0.5;
int y_microsteps = 16;

// --- INTERFACCIA WEB (HTML/CSS/JS) ---
const char HTML_PAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html><html>
<head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FYSETC E4 Control</title>
<style>
  body { font-family: sans-serif; text-align: center; background-color: #1a1a1a; color: #eee; margin: 0; padding: 10px; }
  h2 { color: #f39c12; margin: 10px 0; }
  .card { background-color: #2d2d2d; padding: 10px; margin: 10px auto; max-width: 400px; border-radius: 8px; border: 1px solid #444; }
  
  /* Griglia bottoni gradi */
  .deg-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5px; margin-bottom: 10px; }
  .btn-deg { padding: 10px 0; background-color: #34495e; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
  .btn-deg:active { background-color: #2980b9; transform: translateY(2px); }
  .pos { background-color: #27ae60; }
  .neg { background-color: #c0392b; }

  /* Controlli settings */
  .ctrl-row { display: flex; justify-content: space-between; margin-top: 8px; }
  input, select { padding: 8px; width: 60%; background: #444; color: white; border: 1px solid #555; border-radius: 4px; }
  .btn-set { width: 35%; background-color: #f39c12; border: none; border-radius: 4px; color: white; font-weight: bold; }
  
  .log { font-family: monospace; color: #00ff00; font-size: 12px; margin-top: 5px; min-height: 15px; }
</style>
<script>
  // Configurazione Motori (Standard 1.8 gradi = 200 step/giro)
  const STEPS_PER_REV = 200; 
  
  // Teniamo traccia dei microstep lato JS per fare i calcoli giusti
  var microX = 16;
  var microY = 16;

  function sendCmd(cmd) {
    fetch("/cmd?val=" + encodeURIComponent(cmd))
      .then(r => r.text())
      .then(t => document.getElementById("status").innerText = "> " + t);
  }

  // Muove in gradi: Calcola i passi basandosi sui microstep attuali
  function moveDeg(axis, deg) {
    let u = (axis === 'X') ? microX : microY;
    // Formula: (Gradi / 360) * (StepMotore * Microsteps)
    let steps = Math.round((deg / 360.0) * (STEPS_PER_REV * u));
    sendCmd(axis + steps);
  }

  // Imposta microstep e aggiorna variabile JS
  function setMicro(axis) {
    let val = document.getElementById('m' + axis).value;
    val = parseInt(val);
    if(axis === 'X') microX = val;
    else microY = val;
    sendCmd('S' + axis + val);
  }

  function setCurrent(axis, type) {
    let id = (type === 'C') ? 'c' : 'h'; // C=Run, H=Hold
    let val = document.getElementById(id + axis).value;
    sendCmd(type + axis + val);
  }
</script>
</head>
<body>
  <h2>FYSETC E4 WiFi</h2>
  <div id="status" class="log">Ready</div>

  <div class="card">
    <h3>AXIS X</h3>
    <div class="deg-grid">
      <button class="btn-deg neg" onclick="moveDeg('X', -360)">-360&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('X', -90)">-90&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('X', -10)">-10&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('X', -1)">-1&deg;</button>
      
      <button class="btn-deg pos" onclick="moveDeg('X', 1)">+1&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('X', 10)">+10&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('X', 90)">+90&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('X', 360)">+360&deg;</button>
    </div>

    <div class="ctrl-row">
      <input type="number" id="cX" placeholder="Run mA (600)">
      <button class="btn-set" onclick="setCurrent('X', 'C')">SET mA</button>
    </div>
    <div class="ctrl-row">
      <select id="mX" onchange="setMicro('X')">
        <option value="16" selected>16 Steps</option>
        <option value="32">32 Steps</option>
        <option value="64">64 Steps</option>
        <option value="0">Full</option>
      </select>
      <button class="btn-set" onclick="setMicro('X')">SET STP</button>
    </div>
  </div>

  <div class="card">
    <h3>AXIS Y</h3>
    <div class="deg-grid">
      <button class="btn-deg neg" onclick="moveDeg('Y', -360)">-360&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('Y', -90)">-90&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('Y', -10)">-10&deg;</button>
      <button class="btn-deg neg" onclick="moveDeg('Y', -1)">-1&deg;</button>
      
      <button class="btn-deg pos" onclick="moveDeg('Y', 1)">+1&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('Y', 10)">+10&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('Y', 90)">+90&deg;</button>
      <button class="btn-deg pos" onclick="moveDeg('Y', 360)">+360&deg;</button>
    </div>

    <div class="ctrl-row">
      <input type="number" id="cY" placeholder="Run mA (600)">
      <button class="btn-set" onclick="setCurrent('Y', 'C')">SET mA</button>
    </div>
    <div class="ctrl-row">
      <select id="mY" onchange="setMicro('Y')">
        <option value="16" selected>16 Steps</option>
        <option value="32">32 Steps</option>
        <option value="64">64 Steps</option>
        <option value="0">Full</option>
      </select>
      <button class="btn-set" onclick="setMicro('Y')">SET STP</button>
    </div>
  </div>
</body></html>
)rawliteral";

// --- FUNZIONI DRIVER ---
void apply_current_x() { driverX.rms_current(x_run_ma, x_hold_mult); }
void apply_current_y() { driverY.rms_current(y_run_ma, y_hold_mult); }

// --- PARSER COMANDI (Identico) ---
String parseCommand(String input) {
  input.trim();
  String response = "OK";
  if (input.length() < 2) return "ERR";

  char firstChar = input.charAt(0);
  
  // Movimento Diretto (es. X800 calcolato dalla web ui per 90 gradi)
  if ((firstChar == 'X' || firstChar == 'x' || firstChar == 'Y' || firstChar == 'y') && 
      (isdigit(input.charAt(1)) || input.charAt(1) == '-')) {
      long steps = input.substring(1).toInt();
      if (firstChar == 'X' || firstChar == 'x') { stepperX.move(steps); response = "X: " + String(steps); } 
      else { stepperY.move(steps); response = "Y: " + String(steps); }
      return response;
  }

  // Comandi Config (CX, SX, HX...)
  if (input.length() > 2) {
      char type = firstChar; char axis = input.charAt(1);
      int val = input.substring(2).toInt();

      if (type == 'C' || type == 'c') {
        if (axis == 'X' || axis == 'x') { x_run_ma = val; apply_current_x(); response = "X mA: " + String(val); }
        else { y_run_ma = val; apply_current_y(); response = "Y mA: " + String(val); }
      }
      else if (type == 'H' || type == 'h') {
        float mult = val / 100.0;
        if (axis == 'X' || axis == 'x') { x_hold_mult = mult; apply_current_x(); response = "X Hold: " + String(val) + "%"; }
        else { y_hold_mult = mult; apply_current_y(); response = "Y Hold: " + String(val) + "%"; }
      }
      else if (type == 'S' || type == 's') {
        if (axis == 'X' || axis == 'x') { driverX.microsteps(val); x_microsteps = val; response = "X Micro: " + String(val); }
        else { driverY.microsteps(val); y_microsteps = val; response = "Y Micro: " + String(val); }
      }
  }
  return response;
}

// --- HANDLERS ---
void handleRoot() { server.send(200, "text/html", HTML_PAGE); }
void handleCmd() {
  if (server.hasArg("val")) {
    server.send(200, "text/plain", parseCommand(server.arg("val")));
  } else server.send(400, "text/plain", "Err");
}

void setup() {
  Serial.begin(115200);
  SERIAL_PORT.begin(115200, SERIAL_8N1, DRIVER_UART_RX, DRIVER_UART_TX);

  pinMode(ENABLE_PIN, OUTPUT); digitalWrite(ENABLE_PIN, LOW);

  driverX.begin(); driverX.toff(5); driverX.microsteps(x_microsteps); driverX.pwm_autoscale(true); apply_current_x();
  driverY.begin(); driverY.toff(5); driverY.microsteps(y_microsteps); driverY.pwm_autoscale(true); apply_current_y();

  stepperX.setMaxSpeed(2000); stepperX.setAcceleration(1000);
  stepperY.setMaxSpeed(2000); stepperY.setAcceleration(1000);

  // WIFI RESET & START
  WiFi.disconnect(true); WiFi.softAPdisconnect(true); delay(100);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(ssid, password);
  
  Serial.println("\n--- FYSETC E4 READY ---");
  Serial.print("IP: "); Serial.println(WiFi.softAPIP());

  server.on("/", handleRoot);
  server.on("/cmd", handleCmd);
  server.begin();
  telnetServer.begin(); telnetServer.setNoDelay(true);
}

void loop() {
  stepperX.run();
  stepperY.run();

  if (Serial.available()) Serial.println(parseCommand(Serial.readStringUntil('\n')));
  server.handleClient();
  
  if (telnetServer.hasClient()) {
    if (!telnetClient || !telnetClient.connected()) {
      if(telnetClient) telnetClient.stop();
      telnetClient = telnetServer.available();
    } else telnetServer.available().stop();
  }
  if (telnetClient && telnetClient.available()) {
    String input = telnetClient.readStringUntil('\n');
    if(input.length() > 0) telnetClient.println(parseCommand(input));
  }
}