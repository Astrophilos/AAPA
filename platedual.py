import customtkinter as ctk
import serial
import serial.tools.list_ports
import time
import threading
import os
import glob
import json
import math
from pathlib import Path

# --- CONFIGURAZIONE TEMA ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class AstroController(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- SETUP FINESTRA ---
        self.title("ASTRO COMMANDER PRO - DUAL AXIS EDITION")
        self.geometry("1000x950")
        
        # --- VARIABILI DI STATO ---
        self.ser = None
        self.is_connected = False
        self.polar_monitoring = False 
        self.auto_aligning = False 
        
        # Variabili Motori (Default Nema 17)
        self.steps_per_rev = ctk.IntVar(value=200)
        
        # ASSE X (Azimuth)
        self.x_ms = ctk.IntVar(value=16)
        self.x_run = ctk.IntVar(value=600)
        self.x_hold = ctk.IntVar(value=50)
        self.x_ratio = ctk.DoubleVar(value=1.0)
        self.x_reverse = ctk.BooleanVar(value=False)
        
        # ASSE Y (Altitude)
        self.y_ms = ctk.IntVar(value=16)
        self.y_run = ctk.IntVar(value=600)
        self.y_hold = ctk.IntVar(value=50)
        self.y_ratio = ctk.DoubleVar(value=1.0)
        self.y_reverse = ctk.BooleanVar(value=False)

        # Variabili N.I.N.A
        self.alt_error_var = ctk.StringVar(value="--° --' --\"")
        self.az_error_var = ctk.StringVar(value="--° --' --\"")
        self.last_update_var = ctk.StringVar(value="Status: Waiting for N.I.N.A...")
        
        # Dati Grezzi
        self.raw_alt = None
        self.raw_az = None
        self.last_log_timestamp = 0

        # Variabili Calibrazione & Pilot
        self.calib_status = ctk.StringVar(value="Ready")
        self.calib_result = ctk.StringVar(value="---")
        self.pilot_status = ctk.StringVar(value="Auto-Pilot Standby")

        # --- LAYOUT GRIGLIA ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- COSTRUZIONE UI ---
        self.setup_header()           
        self.setup_axis_panels()      
        self.setup_polar_panel()      
        self.setup_calibration_panel()
        self.setup_log_panel()        
        
        self.refresh_ports()

    # --- HELPER UTILITY ---
    def decimal_to_dms(self, decimal_deg):
        if decimal_deg is None: return "--"
        is_positive = decimal_deg >= 0
        decimal_deg = abs(decimal_deg)
        d = int(decimal_deg)
        m = int((decimal_deg - d) * 60)
        s = (decimal_deg - d - m/60) * 3600
        sign = "+" if is_positive else "-"
        return f"{sign}{d}° {m:02d}' {s:04.1f}\""

    # --- HEADER ---
    def setup_header(self):
        self.header_frame = ctk.CTkFrame(self, corner_radius=10)
        self.header_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.header_frame, text="CONNECTION", font=("Roboto", 14, "bold"), text_color="gray").pack(side="left", padx=15)
        self.port_combo = ctk.CTkComboBox(self.header_frame, width=150); self.port_combo.pack(side="left", padx=5)
        ctk.CTkButton(self.header_frame, text="⟳", width=40, command=self.refresh_ports).pack(side="left", padx=5)
        self.btn_connect = ctk.CTkButton(self.header_frame, text="CONNETTI", fg_color="green", command=self.toggle_connection); self.btn_connect.pack(side="left", padx=15)
        ctk.CTkLabel(self.header_frame, text="Steps/Rev:").pack(side="left", padx=(20, 5))
        ctk.CTkEntry(self.header_frame, textvariable=self.steps_per_rev, width=60).pack(side="left")

    # --- AXIS PANELS ---
    def setup_axis_panels(self):
        self.frame_x = ctk.CTkFrame(self, corner_radius=15)
        self.frame_x.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.create_axis_ui(self.frame_x, "ASSE X (Azimuth)", 'X', self.x_ms, self.x_run, self.x_hold, self.x_ratio, self.x_reverse)

        self.frame_y = ctk.CTkFrame(self, corner_radius=15)
        self.frame_y.grid(row=1, column=1, padx=10, pady=5, sticky="nsew")
        self.create_axis_ui(self.frame_y, "ASSE Y (Altitude)", 'Y', self.y_ms, self.y_run, self.y_hold, self.y_ratio, self.y_reverse)

    def create_axis_ui(self, parent, title, axis_char, v_ms, v_run, v_hold, v_ratio, v_rev):
        ctk.CTkLabel(parent, text=title, font=("Roboto", 20, "bold"), text_color="#3B8ED0").pack(pady=(15, 10))
        
        # Quick Move
        quick_frame = ctk.CTkFrame(parent, fg_color="transparent"); quick_frame.pack(fill="x", padx=10, pady=5)
        btns = [-90, -45, -10, -1, 1, 10, 45, 90]
        btn_grid = ctk.CTkFrame(quick_frame, fg_color="transparent"); btn_grid.pack()
        for i, val in enumerate(btns):
            color = "#992222" if val < 0 else "#228822"
            b = ctk.CTkButton(btn_grid, text=f"{val}°", width=55, height=35, fg_color=color, command=lambda v=val: self.move(axis_char, v))
            b.grid(row=0 if i < 4 else 1, column=i if i < 4 else i-4, padx=3, pady=3)

        # Config
        conf_f = ctk.CTkFrame(parent, fg_color="#2b2b2b"); conf_f.pack(fill="x", padx=15, pady=10)
        ctk.CTkLabel(conf_f, text="SETTINGS", font=("Roboto", 10, "bold")).pack(pady=2)
        
        r_row = ctk.CTkFrame(conf_f, fg_color="transparent"); r_row.pack(pady=2)
        ctk.CTkLabel(r_row, text="Ratio:", width=50).pack(side="left")
        ctk.CTkEntry(r_row, textvariable=v_ratio, width=60).pack(side="left")
        ctk.CTkSwitch(r_row, text="Rev", variable=v_rev, width=50).pack(side="left", padx=10)

        p_row = ctk.CTkFrame(conf_f, fg_color="transparent"); p_row.pack(pady=2)
        ctk.CTkLabel(p_row, text="MS:", width=30).pack(side="left")
        ctk.CTkComboBox(p_row, variable=v_ms, values=["16","32","64"], width=60).pack(side="left")
        ctk.CTkButton(p_row, text="SET", width=40, command=lambda: self.send_cmd(f"S{axis_char}{v_ms.get()}")).pack(side="left", padx=5)

    # --- POLAR PANEL (AUTO PILOT) ---
    def setup_polar_panel(self):
        self.polar_frame = ctk.CTkFrame(self, corner_radius=10, border_width=1, border_color="#555")
        self.polar_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Header
        h_row = ctk.CTkFrame(self.polar_frame, fg_color="transparent"); h_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(h_row, text="N.I.N.A AUTO-PILOT SYSTEM", font=("Roboto", 14, "bold"), text_color="#A020F0").pack(side="left")
        self.btn_polar = ctk.CTkSwitch(h_row, text="Monitor Link", command=self.toggle_polar_monitor, progress_color="#A020F0"); self.btn_polar.pack(side="right")

        # Dati Errori
        data_row = ctk.CTkFrame(self.polar_frame, fg_color="transparent"); data_row.pack(fill="x", padx=10, pady=10)
        
        col_alt = ctk.CTkFrame(data_row, fg_color="transparent"); col_alt.pack(side="left", expand=True, fill="both")
        self.create_error_box(col_alt, "ALTITUDE ERROR", self.alt_error_var, "cyan")
        
        col_az = ctk.CTkFrame(data_row, fg_color="transparent"); col_az.pack(side="left", expand=True, fill="both")
        self.create_error_box(col_az, "AZIMUTH ERROR", self.az_error_var, "orange")

        # --- BOTTONI DI CONTROLLO UNIFICATI ---
        ctrl_row = ctk.CTkFrame(self.polar_frame, fg_color="transparent"); ctrl_row.pack(pady=5)
        
        # Singoli assi (Opzionali)
        ctk.CTkButton(ctrl_row, text="Align ONLY ALT", width=100, fg_color="#333", command=lambda: self.start_auto_pilot('Y')).pack(side="left", padx=5)
        
        # *** TASTO PRINCIPALE DUAL AXIS ***
        self.btn_dual_pilot = ctk.CTkButton(ctrl_row, text="🚀 AUTO ALIGN ALL (DUAL) 🚀", width=200, height=40, fg_color="purple", font=("Roboto", 14, "bold"), command=self.start_dual_pilot)
        self.btn_dual_pilot.pack(side="left", padx=10)
        
        ctk.CTkButton(ctrl_row, text="Align ONLY AZ", width=100, fg_color="#333", command=lambda: self.start_auto_pilot('X')).pack(side="left", padx=5)

        # Pilot Status
        ctk.CTkLabel(self.polar_frame, textvariable=self.pilot_status, font=("Mono", 12, "bold"), text_color="yellow").pack(pady=5)
        ctk.CTkButton(self.polar_frame, text="EMERGENCY STOP", fg_color="red", command=self.stop_auto_pilot).pack(pady=5)

    def create_error_box(self, parent, title, variable, color):
        f = ctk.CTkFrame(parent, fg_color="#222", corner_radius=8); f.pack(fill="x", padx=5)
        ctk.CTkLabel(f, text=title, font=("Roboto", 10, "bold"), text_color="gray").pack(pady=(5,0))
        ctk.CTkLabel(f, textvariable=variable, font=("Mono", 20, "bold"), text_color=color).pack(pady=(0,5))

    # --- CALIBRATION ---
    def setup_calibration_panel(self):
        self.calib_frame = ctk.CTkFrame(self, corner_radius=10, border_width=1, border_color="#444")
        self.calib_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.calib_frame, text="RATIO CALIBRATION LAB", font=("Roboto", 14, "bold"), text_color="yellow").pack(pady=(5,2))
        c_row = ctk.CTkFrame(self.calib_frame, fg_color="transparent"); c_row.pack(pady=5)
        self.calib_axis_combo = ctk.CTkComboBox(c_row, values=["X (Azimuth)", "Y (Altitude)"], width=120); self.calib_axis_combo.pack(side="left", padx=5)
        ctk.CTkButton(c_row, text="START CALIBRATION (360°)", fg_color="yellow", text_color="black", command=self.start_calibration).pack(side="left", padx=15)
        ctk.CTkLabel(c_row, textvariable=self.calib_status, text_color="cyan").pack(side="left", padx=5)
        
        r_row = ctk.CTkFrame(self.calib_frame, fg_color="transparent"); r_row.pack(pady=5)
        ctk.CTkLabel(r_row, textvariable=self.calib_result, font=("Mono", 18, "bold"), text_color="lime").pack(side="left", padx=5)
        ctk.CTkButton(r_row, text="APPLY", width=80, command=self.apply_calibration).pack(side="left", padx=15)

    # --- LOG PANEL ---
    def setup_log_panel(self):
        self.log_frame = ctk.CTkFrame(self, height=120, corner_radius=10)
        self.log_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.log_text = ctk.CTkTextbox(self.log_frame, font=("Courier", 12), text_color="#00ff00", height=80)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text.configure(state="disabled")

    # ================= LOGICA PILOTA =================

    def stop_auto_pilot(self):
        self.auto_aligning = False
        self.pilot_status.set("PILOT ABORTED BY USER")
        self.log("AUTO PILOT STOPPED.")

    # --- START DUAL PILOT (NUOVO) ---
    def start_dual_pilot(self):
        if not self.is_connected or not self.polar_monitoring:
            self.pilot_status.set("Error: Connect & Enable Monitor First")
            return
        if self.raw_alt is None or self.raw_az is None: 
            self.pilot_status.set("Error: No NINA Data yet")
            return
            
        self.auto_aligning = True
        self.pilot_status.set(f"DUAL PILOT ENGAGED (ALT + AZ)")
        threading.Thread(target=self.dual_pilot_loop, daemon=True).start()

    # --- LOOP DUAL PILOT (NUOVO ALGORITMO) ---
    def dual_pilot_loop(self):
        target_error_deg = 0.005 # ~18 arcsec (Soglia di successo)
        gain = 0.8 
        max_attempts = 20
        attempt = 0
        
        self.log(f"--- STARTING DUAL ALIGNMENT ---")

        while self.auto_aligning and attempt < max_attempts:
            # 1. Lettura errori correnti
            curr_az = self.raw_az
            curr_alt = self.raw_alt
            
            # 2. Check Successo Completo
            az_ok = abs(curr_az) < target_error_deg
            alt_ok = abs(curr_alt) < target_error_deg
            
            if az_ok and alt_ok:
                self.pilot_status.set(f"SUCCESS! BOTH AXES ALIGNED!")
                self.log(f"FINAL: AZ={curr_az:.5f}° | ALT={curr_alt:.5f}°")
                break

            self.pilot_status.set(f"Iter {attempt+1}: Moving motors...")
            
            # 3. Calcolo Correzioni (Indipendenti)
            # Muoviamo l'asse solo se è fuori target
            if not az_ok:
                corr_az = -(curr_az * gain)
                self.log(f"Iter {attempt+1} [AZ]: Err {curr_az:.4f} -> Move {corr_az:.4f}")
                self.move('X', corr_az)
            
            if not alt_ok:
                corr_alt = -(curr_alt * gain)
                self.log(f"Iter {attempt+1} [ALT]: Err {curr_alt:.4f} -> Move {corr_alt:.4f}")
                self.move('Y', corr_alt)

            # 4. SETTLING TIME CONDIVISO (15s)
            # Aspettiamo una volta sola per entrambi i motori
            for i in range(15, 0, -1):
                if not self.auto_aligning: return 
                self.pilot_status.set(f"Settling... {i}s")
                time.sleep(1)

            # 5. Attesa Log NINA (Singola attesa per nuova foto)
            self.pilot_status.set(f"Waiting N.I.N.A image analysis...")
            start_ts = self.last_log_timestamp
            wait_timer = 0
            while self.last_log_timestamp == start_ts:
                time.sleep(1)
                wait_timer += 1
                if not self.auto_aligning: return 
                if wait_timer > 120: # Timeout aumentato per platesolving
                    self.pilot_status.set("Error: N.I.N.A Timeout")
                    return
            
            # 6. Check Direzione (Logic Reversal Check)
            # Qui è complesso fare check direzione su due assi, lo facciamo basilare
            new_az = self.raw_az
            new_alt = self.raw_alt
            
            # Se l'errore è aumentato drasticamente su un asse che abbiamo mosso, invertiamo
            if not az_ok and abs(new_az) > abs(curr_az) + 0.01:
                self.log("WARNING: AZ Error Increased! Reversing X logic...")
                self.x_reverse.set(not self.x_reverse.get())

            if not alt_ok and abs(new_alt) > abs(curr_alt) + 0.01:
                self.log("WARNING: ALT Error Increased! Reversing Y logic...")
                self.y_reverse.set(not self.y_reverse.get())
            
            attempt += 1

        self.auto_aligning = False
        if attempt >= max_attempts:
             self.pilot_status.set("Failed: Max attempts reached")

    # --- LOOP PILOTA SINGOLO (LEGACY/BACKUP) ---
    def start_auto_pilot(self, axis):
        if not self.is_connected or not self.polar_monitoring:
            self.pilot_status.set("Error: Connect & Enable Monitor First")
            return
        if self.raw_alt is None: 
            self.pilot_status.set("Error: No NINA Data yet")
            return
            
        self.auto_aligning = True
        self.pilot_status.set(f"PILOT ENGAGED: Aligning {axis}...")
        threading.Thread(target=self.auto_pilot_loop, args=(axis,), daemon=True).start()

    def auto_pilot_loop(self, axis):
        target_error_deg = 0.005 
        gain = 0.8 
        max_attempts = 15
        attempt = 0
        
        self.log(f"--- STARTING SINGLE ALIGN {axis} ---")

        while self.auto_aligning and attempt < max_attempts:
            current_error = self.raw_az if axis == 'X' else self.raw_alt
            
            if abs(current_error) < target_error_deg:
                self.pilot_status.set(f"SUCCESS! Error < {target_error_deg*60:.1f}'")
                break
            
            correction_deg = -(current_error * gain)
            self.pilot_status.set(f"Iter {attempt+1}: Err={current_error:.4f}°. Moving...")
            self.log(f"Pilot Iter {attempt+1}: Error {current_error:.4f}. Fix {correction_deg:.4f}")
            
            self.move(axis, correction_deg)
            
            for i in range(15, 0, -1):
                if not self.auto_aligning: return 
                self.pilot_status.set(f"Settling... {i}s")
                time.sleep(1)

            self.pilot_status.set(f"Waiting N.I.N.A update...")
            start_ts = self.last_log_timestamp
            wait_timer = 0
            while self.last_log_timestamp == start_ts:
                time.sleep(1)
                wait_timer += 1
                if not self.auto_aligning: return 
                if wait_timer > 90:
                    self.pilot_status.set("Error: N.I.N.A Timeout")
                    return
            
            new_error = self.raw_az if axis == 'X' else self.raw_alt
            if abs(new_error) > abs(current_error):
                self.log("WARNING: Error Increased! Reversing Logic...")
                if axis == 'X': self.x_reverse.set(not self.x_reverse.get())
                else: self.y_reverse.set(not self.y_reverse.get())
            
            attempt += 1
        self.auto_aligning = False

    # --- CALIBRATION LOGIC ---
    def start_calibration(self):
        if not self.is_connected or not self.polar_monitoring:
            self.calib_status.set("Error: Connect & Enable NINA first")
            return
        sel = self.calib_axis_combo.get()
        axis = 'X' if "X" in sel else 'Y'
        threading.Thread(target=self.calib_thread, args=(axis,), daemon=True).start()

    def calib_thread(self, axis):
        self.calib_status.set(f"1. Reading Start {axis}...")
        start_val = self.raw_az if axis == 'X' else self.raw_alt
        if start_val is None:
            self.calib_status.set("Err: No NINA Data")
            return

        self.calib_status.set("2. Moving 360 Motor Deg...")
        spr = self.steps_per_rev.get()
        ms = self.x_ms.get() if axis == 'X' else self.y_ms.get()
        steps = spr * ms 
        self.send_cmd(f"{axis}{steps}")
        
        for i in range(20, 0, -1):
            self.calib_status.set(f"Settling... {i}s")
            time.sleep(1)

        self.calib_status.set("Waiting NINA Log...")
        ts = self.last_log_timestamp
        e = 0
        while self.last_log_timestamp == ts:
            time.sleep(1); e+=1
            if e>90: self.calib_status.set("Timeout NINA"); return
            
        end_val = self.raw_az if axis == 'X' else self.raw_alt
        delta = abs(end_val - start_val)
        
        if delta < 0.01:
            self.calib_status.set("Err: Move < 0.01 (Noise)")
            self.log("CALIB: Sky didn't move. Check Clutch/Current.")
            return

        ratio = 360.0 / delta
        self.calib_result.set(f"{ratio:.4f}")
        self.calib_status.set("Success!")
        self.log(f"Calib: Delta={delta:.4f}°. Ratio={ratio:.4f}")

    def apply_calibration(self):
        try:
            r = float(self.calib_result.get())
            if "X" in self.calib_axis_combo.get(): self.x_ratio.set(r)
            else: self.y_ratio.set(r)
            self.log(f"Ratio {r:.4f} applied.")
        except: pass

    # --- MOVIMENTO ---
    def move(self, axis, degrees):
        try:
            spr = self.steps_per_rev.get()
            ms = self.x_ms.get() if axis == 'X' else self.y_ms.get()
            ratio = self.x_ratio.get() if axis == 'X' else self.y_ratio.get()
            rev = self.x_reverse.get() if axis == 'X' else self.y_reverse.get()
            
            if rev: degrees = -degrees
            steps = int((degrees / 360.0) * spr * ms * ratio)
            
            self.send_cmd(f"{axis}{steps}")
            self.log(f"Move {axis} {degrees}° ({steps} steps)")
        except: self.log("Err Move")

    # --- NINA MONITOR ---
    def toggle_polar_monitor(self):
        if self.btn_polar.get() == 1:
            self.polar_monitoring = True
            threading.Thread(target=self.nina_monitor_loop, daemon=True).start()
        else:
            self.polar_monitoring = False

    def nina_monitor_loop(self):
        path = Path(os.path.expanduser("~")) / "Documents" / "N.I.N.A" / "PolarAlignment"
        while self.polar_monitoring:
            try:
                if not path.exists(): time.sleep(5); continue
                files = [f for f in path.glob('*') if f.is_file()]
                if not files: time.sleep(5); continue
                latest = max(files, key=os.path.getctime)
                ts = os.path.getmtime(latest)
                if ts != self.last_log_timestamp:
                    self.parse_nina(latest); self.last_log_timestamp = ts
            except: pass
            time.sleep(1)

    def parse_nina(self, fpath):
        try:
            with open(fpath, 'r', encoding='utf-8') as f: lines = f.readlines()
            for line in reversed(lines):
                if "AltitudeError" in line and "{" in line:
                    data = json.loads(line.split(" - ", 1)[1].strip())
                    self.raw_alt = data.get("AltitudeError", 0)
                    self.raw_az = data.get("AzimuthError", 0)
                    self.alt_error_var.set(self.decimal_to_dms(self.raw_alt))
                    self.az_error_var.set(self.decimal_to_dms(self.raw_az))
                    self.last_update_var.set(f"Upd: {time.strftime('%H:%M:%S')}")
                    return
        except: pass

    # --- UTILS ---
    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"> {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh_ports(self):
        self.port_combo.configure(values=[p.device for p in serial.tools.list_ports.comports()])
        
    def toggle_connection(self):
        if not self.is_connected:
            try:
                self.ser = serial.Serial(self.port_combo.get(), 115200, timeout=1)
                self.is_connected = True; self.btn_connect.configure(fg_color="red", text="DISCONNETTI")
                threading.Thread(target=self.read_serial_loop, daemon=True).start()
                self.log("Connected.")
            except Exception as e: self.log(f"Err: {e}")
        else:
            if self.ser: self.ser.close()
            self.is_connected = False; self.btn_connect.configure(fg_color="green", text="CONNETTI")

    def read_serial_loop(self):
        while self.is_connected:
            try:
                if self.ser.in_waiting:
                    l = self.ser.readline().decode().strip()
                    if l: self.after(0, lambda m=l: self.log(f"RX: {m}"))
            except: break
            
    def send_cmd(self, c):
        if self.is_connected: self.ser.write((c+"\n").encode())

if __name__ == "__main__":
    app = AstroController()
    app.mainloop()