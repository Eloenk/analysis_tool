import os
import sys
import time
import threading
import serial
import csv

class SerialCollector:
    def __init__(self, port='COM3', baudrate=115200, batch_size=50):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_reading = False
        self.is_recording = False
        self.raw_data = [] # stores tuples: (timestamp, duration_us, actual_distance_cm)
        self.read_thread = None
        self.batch_size = batch_size
        self.current_batch_count = 0

    def connect(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_reading = True
            self.read_thread = threading.Thread(target=self._read_serial, daemon=True)
            self.read_thread.start()
            print(f"Connected to ESP32 on {self.port} at {self.baudrate} baud.")
            return True
        except Exception as e:
            print(f"Error connecting to serial port {self.port}: {e}")
            return False

    def send_command(self, cmd):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write((cmd + '\n').encode('utf-8'))
        else:
            print("Cannot send command. Serial port not connected.")

    def _read_serial(self):
        while self.is_reading:
            if self.serial_conn and self.serial_conn.in_waiting > 0:
                try:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    # Print status or info reports from the ESP32
                    if line.startswith("$OK") or line.startswith("$INFO") or line.startswith("$ERROR"):
                        print(f"\nESP32: {line}")
                        
                    elif line.startswith("$DATA,"):
                        parts = line.split(',')
                        if len(parts) >= 4:
                            ts = int(parts[1])
                            duration = int(parts[2])
                            actual = float(parts[3])
                            
                            if self.is_recording:
                                self.raw_data.append((ts, duration, actual))
                                self.current_batch_count += 1
                                
                                # Carriage return progress monitor
                                sys.stdout.write(f"\r[Recording] Batch: {self.current_batch_count}/{self.batch_size} | Total samples: {len(self.raw_data)}")
                                sys.stdout.flush()
                                
                                if self.current_batch_count >= self.batch_size:
                                    self.is_recording = False
                                    self.send_command("STOP")
                                    sys.stdout.write(f"\n[Batch Completed] Collected {self.batch_size} samples at {actual} cm.\n")
                                    sys.stdout.write("Adjust waste height, then type 'start <next_height>' (or 'stop' to save raw data).\n>> ")
                                    sys.stdout.flush()
                except Exception as e:
                    print(f"\nRead error: {e}")
            time.sleep(0.01)

    def start_recording(self, actual_height):
        self.current_batch_count = 0
        self.is_recording = True
        self.send_command(f"START {actual_height}")
        if len(self.raw_data) == 0:
            print(f"Recording started. Collecting batch of {self.batch_size} samples at {actual_height} cm...")
        else:
            print(f"Resuming recording. Collecting next batch of {self.batch_size} samples at {actual_height} cm... (Total samples so far: {len(self.raw_data)})")

    def stop_recording(self):
        self.is_recording = False
        self.send_command("STOP")
        print() # Line break after carriage return
        print(f"Recording stopped. Total data points collected: {len(self.raw_data)}")
        if len(self.raw_data) > 0:
            self.save_raw_data()
        self.raw_data = []

    def reset_data(self):
        self.raw_data = []
        self.current_batch_count = 0
        print("Telemetry buffer reset.")

    def save_raw_data(self):
        os.makedirs('data', exist_ok=True)
        raw_csv_path = 'data/raw_data.csv'
        with open(raw_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'duration_us', 'actual_distance'])
            writer.writerows(self.raw_data)
        print(f"Raw telemetry saved to {raw_csv_path}")
        print("You can now run 'data_analyser.py' to process filters and generate graphs.")

    def disconnect(self):
        self.is_reading = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("Disconnected.")

def main():
    port = input("Enter serial port (default COM3): ").strip() or 'COM3'
    collector = SerialCollector(port=port)
    if not collector.connect():
        sys.exit(1)

    try:
        while True:
            choice = input("\nCommands: start <height_cm>, stop, reset, exit\n>> ").strip()
            if choice.startswith("start "):
                try:
                    height = float(choice.split()[1])
                    collector.start_recording(height)
                except ValueError:
                    print("Invalid distance value.")
            elif choice == "stop":
                collector.stop_recording()
            elif choice == "reset":
                collector.reset_data()
            elif choice == "exit":
                break
            else:
                collector.send_command(choice)
    finally:
        collector.disconnect()

if __name__ == "__main__":
    main()
