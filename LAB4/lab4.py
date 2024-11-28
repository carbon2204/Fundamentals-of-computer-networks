import serial
import threading
import time
import random
from tkinter import Tk, Label, Button, Entry, StringVar, Text, Scrollbar, END, OptionMenu, messagebox, Frame

# Параметры передачи и эмуляции
n = 5  
FLAG = f"${chr(ord('a') + n)}"
DATA_LENGTH = n + 1
ESCAPE_BYTE = b'\x1b'
FLAG_BYTE = b'$'
CRC_POLYNOMIAL = 0x1D

CHANNEL_BUSY_PROBABILITY = 0.5
COLLISION_PROBABILITY = 0.6

total_bytes = 0  # Общее количество переданных байт

JAM_SIGNAL = b'JAM'  # Определение jam-сигнала


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

def is_channel_busy():
    """Эмуляция занятости канала."""
    return random.random() < CHANNEL_BUSY_PROBABILITY

def is_collision_occurred():
    """Эмуляция коллизии."""
    return random.random() < COLLISION_PROBABILITY

def calculate_backoff(attempt):
    """Рассчет задержки (backoff) с учетом номера попытки."""
    k = min(attempt, 10)  # k = min(n, 10), где n — номер попытки
    return random.uniform(0, (2 ** k) - 1) / 100  # Задержка в миллисекундах


def jam_signal():
    """Отправка jam-сигнала."""
    text_debug.insert(END, "Jam-сигнал отправлен!\n")
    text_debug.see(END)
    time.sleep(0.1)  # Пауза перед отправкой
    ser1.write(JAM_SIGNAL)  # Отправляем jam-сигнал


def send_frame_with_csma_cd(frame):
    """Отправка кадра с использованием CSMA/CD."""
    global total_bytes
    jam_attempts = 0  # Счётчик попыток

    while jam_attempts < 2:  
        if not is_channel_busy():
            if is_collision_occurred():
                # Коллизия: отправляем jam-сигнал
                jam_signal()
                jam_attempts += 1  # Увеличиваем счётчик попыток
                display_frame_status(frame, collision_occurred=True)

                # Розыгрыш задержки (backoff)
                backoff = calculate_backoff(jam_attempts)  # Передаем номер попытки
                text_debug.insert(END, f"Коллизия {jam_attempts}, ожидание {backoff:.3f} сек.\n")
                text_debug.see(END)
                time.sleep(backoff)  # Задержка перед повторной попыткой
            else:
                # Успешная передача кадра
                ser1.write(frame)
                display_frame_status(frame, collision_occurred=False)
                total_bytes += len(frame)
                update_state(len(frame))
                break  # Завершаем передачу
        else:
            # Канал занят, повторная попытка
            text_debug.insert(END, "Канал занят, ожидание...\n")
            text_debug.see(END)
            time.sleep(0.5)

    if jam_attempts >= 2:
        # Если превышено число попыток, игнорируем кадр
        text_debug.insert(END, "Кадр проигнорирован после 2 попыток.\n")
        text_debug.see(END)


def display_frame_status(frame, collision_occurred):
    """Отображение статуса передачи кадра."""
    try:
        # Декодируем флаг (первые два байта)
        flag = frame[:2].decode('utf-8')

        # Преобразуем адреса назначения и источника из 1 байта в целые числа
        dest_addr = frame[2]  # 1-байтовый адрес
        src_addr = frame[3]   # 1-байтовый адрес

        # Декодируем полезные данные
        data = frame[4:4 + DATA_LENGTH].decode('utf-8').rstrip('\x00')

        # Получаем FCS как шестнадцатеричную строку
        received_fcs = frame[4 + DATA_LENGTH:].hex()

        # Отображаем статус передачи: + при коллизии, - при успешной передаче
        status = "+" if collision_occurred else "-"
        text_output.insert(
            END, f"{flag} | Dest: {dest_addr} | Src: {src_addr} | "
                 f"Data: {data} | FCS: {received_fcs} [{status}]\n"
        )
        text_output.see(END)
    except UnicodeDecodeError:
        text_output.insert(END, "Ошибка декодирования данных\n")
        text_output.see(END)



def send_data():
    """Обработка отправки данных с использованием CSMA/CD."""
    message = entry_message.get()
    if message:
        try:
            frame = create_frame(message, send_var.get(), receive_var.get())
            if frame is not None:  # Продолжаем, только если кадр создан успешно
                threading.Thread(target=send_frame_with_csma_cd, args=(frame,), daemon=True).start()
                entry_message.set("")  # Очистка поля ввода
        except serial.SerialException as e:
            messagebox.showerror("Ошибка отправки", str(e))


def create_frame(data, source_port, dest_port):
    """Создание кадра с флагом, адресами, данными и FCS."""
    flag = b'$f'  # Фиксированный флаг для предсказуемости

    try:
        # Извлекаем последние символы портов и преобразуем их в числа
        destination_address = int(dest_port[-1])  # Например, "1" -> 1
        source_address = int(source_port[-1])  # Например, "2" -> 2
    except ValueError:
        messagebox.showerror("Ошибка порта", "Некорректный номер порта!")
        return None  # Прерываем создание кадра при ошибке

    # Преобразуем адреса в 1-байтовые значения (0-255)
    destination_address = destination_address.to_bytes(1, 'big')
    source_address = source_address.to_bytes(1, 'big')

    # Кодируем данные и вычисляем контрольную сумму (FCS)
    data_bytes = data.encode('utf-8').ljust(DATA_LENGTH, b'\x00')  # Заполнение до нужной длины
    fcs = crc8(data_bytes)  # Вычисляем CRC-8

    # Формируем кадр: флаг + адреса + данные + FCS
    frame = flag + destination_address + source_address + data_bytes + fcs
    return byte_stuffing(frame)  # Применяем экранирование



def byte_stuffing(frame):
    """Экранирование флага и управляющих символов."""
    return frame.replace(ESCAPE_BYTE, ESCAPE_BYTE + ESCAPE_BYTE).replace(FLAG_BYTE, ESCAPE_BYTE + FLAG_BYTE)

def read_data():
    """Чтение данных с COM-порта."""
    while True:
        try:
            if ser2.in_waiting > 0:
                frame = byte_destuffing(ser2.read(ser2.in_waiting))

                if frame == JAM_SIGNAL:
                    # Обнаружен jam-сигнал
                    text_output.insert(END, "Обнаружен jam-сигнал! Коллизия произошла.\n")
                    text_output.see(END)
                else:
                    # Обычный кадр
                    display_frame_status(frame, collision_occurred=False)

            time.sleep(0.1)
        except serial.SerialException as e:
            messagebox.showerror("Ошибка приёма", str(e))
            break




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

def update_state(bytes_sent):
    """Обновление состояния передачи."""
    state_label.config(text=f"Скорость: {ser1.baudrate} бод | Передано байт: {total_bytes}")

def start_program():
    """Запуск программы и открытие портов."""
    global ser1, ser2
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
    """Обновление направлений портов."""
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
