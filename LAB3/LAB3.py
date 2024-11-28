import serial
import threading
import time
import random
from tkinter import Tk, Label, Button, Entry, StringVar, Text, Scrollbar, END, OptionMenu, messagebox, Frame

n = 5  
FLAG = f"${chr(ord('a') + n)}"
DATA_LENGTH = n + 1
ESCAPE_BYTE = b'\x1b'
FLAG_BYTE = b'$'
CRC_POLYNOMIAL = 0x1D

def crc8(data):
    """Вычисление CRC-8 для данных."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ CRC_POLYNOMIAL
            else:
                crc <<= 1
            crc &= 0xFF
    return crc.to_bytes(1, 'big')

def correct_single_error(data, received_fcs, polynomial=0x1D):
    """Исправление одиночной ошибки в данных."""
    for i in range(len(data)):
        for bit in range(8):
            # Инвертируем каждый бит по очереди
            modified_data = bytearray(data)
            modified_data[i] ^= (1 << bit)
            
            # Вычисляем CRC для модифицированных данных
            calculated_fcs = crc8(modified_data)
            
            # Проверяем, совпадает ли вычисленный FCS с переданным
            if calculated_fcs == received_fcs:
                return modified_data, True  # Ошибка исправлена
            
    return data, False  # Ошибка не исправлена

def display_received_data(frame):
    """Отображение принятого кадра в интерфейсе."""
    try:
        flag = frame[:2].decode('utf-8')
        dest_addr = int.from_bytes(frame[2:3], 'big')
        src_addr = int.from_bytes(frame[3:4], 'big')
        data = frame[4:4 + DATA_LENGTH].decode('utf-8').rstrip('\x00')
        received_fcs = frame[4 + DATA_LENGTH:]
        calculated_fcs = crc8(frame[4:4 + DATA_LENGTH])

        if received_fcs != calculated_fcs:
            # Если FCS некорректен, попробуем исправить одиночную ошибку
            corrected_data, error_fixed = correct_single_error(frame[4:4 + DATA_LENGTH], received_fcs)
            if error_fixed:
                data = corrected_data.decode('utf-8').rstrip('\x00')
                status = "Ошибка исправлена"
            else:
                status = "Ошибка FCS, не удалось исправить"
        else:
            status = "FCS корректен"

        text_output.insert(END, f"{flag} | Dest: {dest_addr} | Src: {src_addr} | "
                                f"Data: {data} | FCS: {received_fcs.hex()} / {calculated_fcs.hex()} [{status}]\n")
        text_output.see(END)
    except UnicodeDecodeError:
        text_output.insert(END, "Ошибка декодирования данных\n")
        text_output.see(END)

def create_frame(data, source_port, dest_port):
    """Создание кадра с флагом, адресами, данными и FCS."""
    flag = FLAG.encode('utf-8')
    destination_address = int(dest_port[-1]).to_bytes(1, 'big')
    source_address = int(source_port[-1]).to_bytes(1, 'big')
    data_bytes = data.encode('utf-8').ljust(DATA_LENGTH, b'\x00')
    fcs = crc8(data_bytes)  # Вычисление FCS (CRC-8)
    frame = flag + destination_address + source_address + data_bytes + fcs
    return byte_stuffing(frame)

def byte_stuffing(frame):
    """Экранирование флага и управляющих символов."""
    return frame.replace(ESCAPE_BYTE, ESCAPE_BYTE + ESCAPE_BYTE).replace(FLAG_BYTE, ESCAPE_BYTE + FLAG_BYTE)

def byte_destuffing(stuffed_frame):
    """Удаление экранирующих байтов."""
    result = b''
    i = 0
    while i < len(stuffed_frame):
        if stuffed_frame[i:i+1] == ESCAPE_BYTE and i + 1 < len(stuffed_frame):
            i += 1
        result += stuffed_frame[i:i+1]
        i += 1
    return result

def corrupt_data(data):
    """Случайное искажение одного бита в данных."""
    if random.random() < 0.7:  # 70% вероятность искажения
        byte_index = random.randint(0, len(data) - 1)
        bit_index = random.randint(0, 7)
        corrupted_byte = data[byte_index] ^ (1 << bit_index)
        data = data[:byte_index] + bytes([corrupted_byte]) + data[byte_index + 1:]
    return data

def send_data():
    """Отправка данных через COM-порт."""
    message = entry_message.get()
    if message:
        try:
            frame = create_frame(message, send_var.get(), receive_var.get())
            ser1.write(frame)
            update_state(len(frame))
            entry_message.set("")  # Очистка поля ввода
        except serial.SerialException as e:
            messagebox.showerror("Ошибка отправки", str(e))

def read_data():
    """Чтение данных с COM-порта."""
    while True:
        try:
            if ser2.in_waiting > 0:
                frame = byte_destuffing(ser2.read(ser2.in_waiting))
                corrupted_data = corrupt_data(frame[4:4 + DATA_LENGTH])
                frame = frame[:4] + corrupted_data + frame[4 + DATA_LENGTH:]
                display_received_data(frame)
            time.sleep(0.1)
        except serial.SerialException as e:
            messagebox.showerror("Ошибка приёма", str(e))
            break

def display_received_data(frame):
    """Отображение принятого кадра с ошибкой и исправленного кадра в интерфейсе."""
    try:
        flag = frame[:2].decode('utf-8')
        dest_addr = int.from_bytes(frame[2:3], 'big')
        src_addr = int.from_bytes(frame[3:4], 'big')
        data = frame[4:4 + DATA_LENGTH].decode('utf-8').rstrip('\x00')
        received_fcs = frame[4 + DATA_LENGTH:]
        calculated_fcs = crc8(frame[4:4 + DATA_LENGTH])

        # Сначала выводим принятый кадр как есть
        status = "Ошибка FCS" if received_fcs != calculated_fcs else "FCS корректен"
        text_output.insert(END, f"Принято | {flag} | Dest: {dest_addr} | Src: {src_addr} | "
                                f"Data: {data} | FCS: {received_fcs.hex()} / {calculated_fcs.hex()} [{status}]\n")
        text_output.see(END)

        # Если обнаружена ошибка FCS, пытаемся исправить
        if received_fcs != calculated_fcs:
            corrected_data, error_fixed = correct_single_error(frame[4:4 + DATA_LENGTH], received_fcs)
            if error_fixed:
                # Если ошибка исправлена, заново декодируем данные
                corrected_data_str = corrected_data.decode('utf-8').rstrip('\x00')
                calculated_fcs = crc8(corrected_data)
                status = "Ошибка исправлена"
                text_output.insert(END, f"Исправлено | {flag} | Dest: {dest_addr} | Src: {src_addr} | "
                                        f"Data: {corrected_data_str} | FCS: {received_fcs.hex()} / {calculated_fcs.hex()} [{status}]\n")
            else:
                status = "Ошибка не исправлена"
        text_output.see(END)
    except UnicodeDecodeError:
        text_output.insert(END, "Ошибка декодирования данных\n")
        text_output.see(END)

def update_state(bytes_sent):
    """Обновление состояния передачи."""
    global total_bytes
    total_bytes += bytes_sent
    state_label.config(text=f"Скорость: {ser1.baudrate} бод | Передано байт: {total_bytes}")

def start_program():
    """Запуск программы и открытие портов."""
    global ser1, ser2, total_bytes
    total_bytes = 0
    try:
        ser1 = serial.Serial(send_var.get(), baudrate=int(baudrate_var.get()), timeout=1)
        ser2 = serial.Serial(receive_var.get(), baudrate=int(baudrate_var.get()), timeout=1)
        threading.Thread(target=read_data, daemon=True).start()
        update_state(0)
    except serial.SerialException as e:
        messagebox.showerror("Ошибка порта", str(e))

def close_ports():
    """Закрытие портов при завершении программы."""
    if 'ser1' in globals() and ser1.is_open:
        ser1.close()
    if 'ser2' in globals() and ser2.is_open:
        ser2.close()

def update_ports_direction():
    """Обновление направлений портов в зависимости от выбора."""
    selected_direction = direction_var.get()
    if selected_direction == "1 -> 2":
        send_var.set("COM1")
        receive_var.set("COM2")
    elif selected_direction == "5 <- 6":
        send_var.set("COM6")
        receive_var.set("COM5")

# Интерфейс программы
root = Tk()
root.title("COM-порты: Передача и приём данных")
root.geometry("800x600")
root.configure(bg="#FFB6C1")
root.resizable(False, False)

frame_top = Frame(root, bg="#FFB6C1")
frame_top.pack(pady=20, padx=20, fill="x")

Label(frame_top, text="Выберите направление передачи данных:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
direction_var = StringVar(root)
direction_var.set("1 -> 2")
direction_var.trace("w", lambda *args: update_ports_direction())
direction_menu = OptionMenu(frame_top, direction_var, "1 -> 2", "5 <- 6")
direction_menu.grid(row=0, column=1, padx=5, pady=5)

Label(frame_top, text="Порт для отправки данных:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=5)
send_var = StringVar(root)
send_label = Label(frame_top, textvariable=send_var, bg="#FFB6C1", fg="black", font=("Arial", 12))
send_label.grid(row=1, column=1, padx=5, pady=5)

Label(frame_top, text="Порт для получения данных:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=2, column=0, sticky="w", pady=5)
receive_var = StringVar(root)
receive_label = Label(frame_top, textvariable=receive_var, bg="#FFB6C1", fg="black", font=("Arial", 12))
receive_label.grid(row=2, column=1, padx=5, pady=5)

Label(frame_top, text="Выберите скорость передачи данных (бод):", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=3, column=0, sticky="w", pady=5)
baudrate_var = StringVar(root)
baudrate_var.set("9600")
baudrate_menu = OptionMenu(frame_top, baudrate_var, "9600", "19200", "38400", "57600", "115200")
baudrate_menu.grid(row=3, column=1, padx=5, pady=5)

frame_middle = Frame(root, bg="#FFB6C1")
frame_middle.pack(pady=10, padx=20, fill="x")

Label(frame_middle, text="Введите сообщение для отправки:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
entry_message = StringVar()
message_entry = Entry(frame_middle, textvariable=entry_message, width=60, bg="white", fg="black")
message_entry.grid(row=1, column=0, padx=5, pady=5)

send_button = Button(frame_middle, text="Отправить", command=send_data, bg="white", fg="black", padx=20, pady=5, font=("Arial", 12))
send_button.grid(row=1, column=1, padx=10)

frame_bottom = Frame(root, bg="#FFB6C1")
frame_bottom.pack(pady=10, padx=20, fill="x")

Label(frame_bottom, text="Принятые данные:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
text_output = Text(frame_bottom, height=10, width=40, bg="white", fg="black", insertbackground='black')
text_output.grid(row=1, column=0, padx=5, pady=5)

scrollbar = Scrollbar(frame_bottom, command=text_output.yview)
scrollbar.grid(row=1, column=1, sticky='ns')
text_output.config(yscrollcommand=scrollbar.set)

Label(frame_bottom, text="Отладочная информация:", bg="#FFB6C1", fg="black", font=("Arial", 12)).grid(row=0, column=2, sticky="w", pady=5)
text_debug = Text(frame_bottom, height=10, width=40, bg="white", fg="black", insertbackground='black')
text_debug.grid(row=1, column=2, padx=5, pady=5)

scrollbar_debug = Scrollbar(frame_bottom, command=text_debug.yview)
scrollbar_debug.grid(row=1, column=3, sticky='ns')
text_debug.config(yscrollcommand=scrollbar_debug.set)

frame_bottom_buttons = Frame(root, bg="#FFB6C1")
frame_bottom_buttons.pack(pady=20, padx=20, fill="x")

start_button = Button(frame_bottom_buttons, text="Запустить", command=start_program, bg="white", fg="black", padx=20, pady=5, font=("Arial", 12))
start_button.pack(side="left", padx=5)

state_label = Label(frame_bottom_buttons, text="Скорость: неизвестно, Передано байт: 0", bg="#FFB6C1", fg="black", font=("Arial", 12))
state_label.pack(side="right")

root.protocol("WM_DELETE_WINDOW", lambda: [close_ports(), root.destroy()])
root.mainloop()
