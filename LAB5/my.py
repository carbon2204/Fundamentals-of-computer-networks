import threading
import tkinter as tk
import time
import queue
import random

# Константа многочлена для CRC-8
CRC_POLYNOMIAL = 0x1D

class Station:
    def __init__(self, name, ring, priority=1):
        self.name = name
        self.ring = ring
        self.priority = priority
        self.window = None
        self.token = False
        self.monitor = False
        self.is_active = True
        self.address = name

    def create_window(self):
        self.window = tk.Toplevel()
        self.window.title(f"Station {self.name}")

        self.input_text = tk.Text(self.window, height=5, width=40)
        self.input_text.pack()

        self.send_button = tk.Button(self.window, text="Send", command=self.send_message)
        self.send_button.pack()

        self.output_text = tk.Text(self.window, height=10, width=40)
        self.output_text.pack()

        self.address_label = tk.Label(self.window, text="Destination Address")
        self.address_label.pack()
        self.address_var = tk.StringVar(self.window)
        self.address_entry = tk.Entry(self.window, textvariable=self.address_var)
        self.address_entry.pack()

        self.priority_var = tk.StringVar(self.window)
        self.priority_var.set(str(self.priority))
        self.priority_entry = tk.Entry(self.window, textvariable=self.priority_var)
        self.priority_entry.pack()
        self.priority_entry.bind("<FocusOut>", self.update_priority)

        self.priority_label = tk.Label(self.window, text="Priority (1 - Low, 2 - High)")
        self.priority_label.pack()

        self.monitor_button = tk.Button(self.window, text="Become Monitor", command=self.become_monitor)
        self.monitor_button.pack()

        self.duplicate_token_button = tk.Button(self.window, text="Create Duplicate Token", command=self.create_duplicate_token)
        self.duplicate_token_button.pack()

        self.active_button = tk.Button(self.window, text="Activate/Deactivate", command=self.toggle_active)
        self.active_button.pack()

    def send_message(self):
        message = self.input_text.get("1.0", tk.END).strip()
        destination = self.address_var.get().strip()
        if message and destination:
            blocks = [message[i:i+20] for i in range(0, len(message), 20)]
            for i, block in enumerate(blocks):
                packet = {
                    'sd': self.compute_sd(),
                    'ac': self.compute_ac(),
                    'fc': self.compute_fc(),
                    'da': destination,
                    'sa': self.name,
                    'priority': int(self.priority_var.get()) if self.priority_var.get().isdigit() else self.priority,
                    'ri': self.compute_ri(),
                    'sequence': i + 1,
                    'info': block,
                    'fcs': self.compute_fcs(block),  # Вычисляем CRC-8 для блока данных
                    'ed': self.compute_ed(),
                    'fs': self.compute_fs()
                }
                self.ring.put(packet)

    def receive_message(self, packet):
        if packet['da'] == self.name:
            self.output_text.insert(tk.END, f"Received Frame:\n"
                                          f"SD: {packet['sd']}\n"
                                          f"AC: {packet['ac']}\n"
                                          f"FC: {packet['fc']}\n"
                                          f"DA: {packet['da']}\n"
                                          f"SA: {packet['sa']}\n"
                                          f"RI: {packet['ri']}\n"
                                          f"Sequence: {packet['sequence']}\n"
                                          f"Data: {packet['info']}\n"
                                          f"FCS: {packet['fcs'].hex()}\n"
                                          f"ED: {packet['ed']}\n"
                                          f"FS: {packet['fs']}\n\n")
        else:
            self.ring.put(packet)

    def become_monitor(self):
        if not self.is_active:
            self.output_text.insert(tk.END, "Cannot become monitor, station is inactive.\n")
            return
        if self.monitor:
            return
        self.monitor = True
        self.ring.monitor_station = self
        self.ring.log_debug(f"Station {self.name} has become the monitor.")
        self.output_text.insert(tk.END, "This station is now the monitor.\n")

    def create_duplicate_token(self):
        if self.is_active:
            self.token = True
            self.ring.log_debug(f"Station {self.name} created a duplicate token manually.")

    def toggle_active(self):
        self.is_active = not self.is_active
        status = "active" if self.is_active else "inactive"
        self.output_text.insert(tk.END, f"Station is now {status}.\n")
        if not self.is_active and self.monitor:
            self.monitor = False
            self.ring.monitor_station = None
            self.ring.log_debug(f"Station {self.name} (monitor) is now inactive. A new monitor will be selected.")

    def update_priority(self, event):
        if self.priority_var.get().isdigit():
            self.priority = int(self.priority_var.get())

    def start(self, root):
        root.after(0, self.create_window)

    # Calculation methods for each field
    def compute_sd(self):
        return "7E"  # Fixed start delimiter

    def compute_ac(self):
        P = 1 if self.priority == 2 else 0  # Priority bit
        T = 1  # Assume this is a data frame
        M = 1 if self.monitor else 0  # Marker bit if this station is the monitor
        R = 0  # Reserved bits
        return f"{P}{T}{M}{R:05b}"  # Return as a binary string with zero-padded reserved bits

    def compute_fc(self):
        return "08"  # Standard frame control

    def compute_ri(self):
        return hex(random.randint(0x100, 0xFFF))  # Random routing ID for demonstration

    def compute_fcs(self, data):
        """Вычисление CRC-8 для данных."""
        crc = 0
        for byte in data.encode():  # Преобразуем данные в байты для вычисления
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ CRC_POLYNOMIAL
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc.to_bytes(1, 'big')  # Возвращаем FCS в виде одного байта

    def compute_ed(self):
        return "7E"  # Fixed end delimiter

    def compute_fs(self):
        A = 1  # Address recognized flag
        C = 1  # Frame copied flag
        reserved = 0  # Reserved bits
        return f"{A}{reserved:02b}{C}{A}{reserved:02b}{C}"  # Return as binary with duplicated flags

class TokenRing:
    def __init__(self):
        self.stations = []
        self.queue = queue.Queue()
        self.token = True
        self.current_station = 0
        self.monitor_station = None
        self.debug_window = None
        self.last_token_time = time.time()

    def add_station(self, station):
        self.stations.append(station)

    def run(self):
        self.create_debug_window()
        while True:
            if self.monitor_station is None:
                self.assign_new_monitor()

            if self.token:
                current = self.stations[self.current_station]
                if current.is_active:
                    current.token = True
                    processed = False
                    for _ in range(self.queue.qsize()):
                        packet = self.queue.get()
                        destination_station = next((s for s in self.stations if s.name == packet['da']), None)
                        source_station = next((s for s in self.stations if s.name == packet['sa']), None)
                        if destination_station and source_station and source_station.priority >= destination_station.priority:
                            self.log_debug(f"Token at Station {current.name}. Packet from {packet['sa']} to {packet['da']}.")
                            if current.name == destination_station.name:
                                current.receive_message(packet)
                            else:
                                self.queue.put(packet)
                            processed = True
                            break
                        else:
                            self.queue.put(packet)
                            self.log_debug(f"Token at Station {current.name}. Packet priority too high for destination, re-queueing.")
                    if not processed:
                        self.log_debug(f"Token at Station {current.name}. No packets to process.")
                else:
                    self.log_debug(f"Station {current.name} is inactive. Skipping.")

                if current == self.monitor_station:
                    self.check_token()

                current.token = False
                self.current_station = (self.current_station + 1) % len(self.stations)
                self.token = True
                self.last_token_time = time.time()
                time.sleep(3)

    def put(self, packet):
        self.queue.put(packet)

    def check_token(self):
        current_time = time.time()
        if current_time - self.last_token_time > 5:
            self.log_debug("Monitor detected lost token. Generating new token.")
            self.token = True
            self.log_debug("New token generated by monitor.")
            self.last_token_time = current_time

        active_tokens = sum(1 for station in self.stations if station.token)
        if active_tokens > 1:
            self.log_debug("Monitor detected multiple tokens. Removing excess tokens.")
            for station in self.stations:
                station.token = False
            self.token = True
            self.log_debug("All excess tokens removed. Only one token now active.")

    def assign_new_monitor(self):
        for station in self.stations:
            if station.is_active:
                self.monitor_station = station
                station.monitor = True
                self.log_debug(f"Station {station.name} has become the new monitor.")
                break

    def create_debug_window(self):
        self.debug_window = tk.Toplevel()
        self.debug_window.title("Debug Window")
        self.debug_output = tk.Text(self.debug_window, height=15, width=50)
        self.debug_output.pack()
        self.debug_window.after(0, self.debug_window.mainloop)

    def log_debug(self, message):
        if self.debug_output:
            self.debug_output.insert(tk.END, f"{message}\n")
            self.debug_output.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    ring = TokenRing()

    station1 = Station("A", ring, priority=1)
    station2 = Station("B", ring, priority=1)
    station3 = Station("C", ring, priority=2)

    ring.add_station(station1)
    ring.add_station(station2)
    ring.add_station(station3)

    threading.Thread(target=ring.run, daemon=True).start()

    station1.start(root)
    station2.start(root)
    station3.start(root)

    root.mainloop()
