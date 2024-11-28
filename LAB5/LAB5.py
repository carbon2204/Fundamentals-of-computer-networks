import tkinter as tk
import threading
import time

# Параметры кольцевой топологии
NUM_STATIONS = 3
TOKEN_TIMEOUT = 5  # Тайм-аут токена в секундах
DATA_LENGTH = 5    # Длина данных в блоке
FLAG = b'$'
CRC_POLYNOMIAL = 0x1D

# Глобальные переменные
token_holder = 0
monitor_station = 0
station_list = []

# Функция для расчета CRC-8
def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc << 1) ^ CRC_POLYNOMIAL if crc & 0x80 else crc << 1
            crc &= 0xFF
    return crc.to_bytes(1, 'big')

# Класс для эмуляции станции
class Station:
    def __init__(self, station_id, root, debug_output):
        self.station_id = station_id
        self.root = root
        self.debug_output = debug_output
        self.has_token = (station_id == token_holder)
        self.is_monitor = False
        self.incoming_data = []

        # Интерфейс станции
        self.window = tk.Toplevel(root)
        self.window.title(f"Station {station_id}")
        self.window.geometry("400x300")

        # Ввод сообщения
        self.message_entry = tk.Entry(self.window, width=50)
        self.message_entry.pack(pady=10)

        # Выбор станции назначения
        self.destination_var = tk.IntVar(value=(station_id + 1) % NUM_STATIONS)
        tk.Label(self.window, text="Destination:").pack()
        tk.OptionMenu(self.window, self.destination_var, *range(NUM_STATIONS)).pack()

        # Установка приоритета
        self.priority_var = tk.IntVar(value=0)
        tk.Label(self.window, text="Priority:").pack()
        tk.OptionMenu(self.window, self.priority_var, 0, 1).pack()

        # Кнопка отправки
        self.send_button = tk.Button(self.window, text="Send", command=self.send_data)
        self.send_button.pack(pady=10)

        # Вывод принятых сообщений
        self.text_output = tk.Text(self.window, height=10, width=50)
        self.text_output.pack()

        # Поток обработки токена
        threading.Thread(target=self.token_handler, daemon=True).start()

    # Функция отправки сообщения
    def send_data(self):
        if not self.has_token:
            self.debug_output.insert(tk.END, f"Station {self.station_id}: Нет токена для отправки сообщения\n")
            return
        message = self.message_entry.get()
        destination = self.destination_var.get()
        priority = self.priority_var.get()

        if message:
            frame = self.create_frame(message, destination, priority)
            station_list[destination].receive_data(frame)
            self.debug_output.insert(tk.END, f"Station {self.station_id} отправила сообщение: {message} в Station {destination} с приоритетом {priority}\n")
            self.message_entry.delete(0, tk.END)

        self.pass_token()

    # Создание кадра с данными
    def create_frame(self, data, dest, priority):
        flag = FLAG
        destination = dest.to_bytes(1, 'big')
        source = self.station_id.to_bytes(1, 'big')
        priority_byte = priority.to_bytes(1, 'big')
        data_bytes = data.encode('utf-8').ljust(DATA_LENGTH, b'\x00')
        fcs = crc8(data_bytes)
        frame = flag + destination + source + priority_byte + data_bytes + fcs + flag
        return frame

    # Получение и отображение данных
    def receive_data(self, frame):
        try:
            dest_addr = frame[1]
            src_addr = frame[2]
            priority = frame[3]
            data = frame[4:4 + DATA_LENGTH].decode('utf-8').rstrip('\x00')
            received_fcs = frame[4 + DATA_LENGTH:5 + DATA_LENGTH]
            calculated_fcs = crc8(frame[4:4 + DATA_LENGTH])

            if received_fcs == calculated_fcs:
                status = "FCS корректен"
            else:
                status = "Ошибка FCS"

            self.text_output.insert(tk.END, f"Получено от Station {src_addr} | Data: {data} | {status}\n")
            self.debug_output.insert(tk.END, f"Station {self.station_id} приняла данные от Station {src_addr}: {data}\n")
        except Exception as e:
            self.debug_output.insert(tk.END, f"Ошибка при приеме данных: {e}\n")

    # Передача токена
    def pass_token(self):
        global token_holder
        token_holder = (self.station_id + 1) % NUM_STATIONS
        self.has_token = False
        station_list[token_holder].has_token = True
        self.debug_output.insert(tk.END, f"Station {self.station_id} передала токен Station {token_holder}\n")

    # Обработчик токена
    def token_handler(self):
        while True:
            if self.has_token:
                self.debug_output.insert(tk.END, f"Station {self.station_id} получила токен\n")
                time.sleep(TOKEN_TIMEOUT)
                self.pass_token()
            if self.is_monitor:
                self.monitor_token()

    # Мониторинг и восстановление токена
    def monitor_token(self):
        global token_holder
        if not self.has_token:
            token_holder = self.station_id
            self.has_token = True
            self.debug_output.insert(tk.END, f"Station {self.station_id} (Monitor) перезапустила токен\n")

# Создание главного окна и отладочного окна
root = tk.Tk()
root.title("Token Ring Network")

debug_window = tk.Toplevel(root)
debug_window.title("Debug Window")
debug_output = tk.Text(debug_window, height=20, width=70)
debug_output.pack()

# Инициализация станций и добавление в список
station_list = [Station(i, root, debug_output) for i in range(NUM_STATIONS)]

# Запуск GUI
root.mainloop()
