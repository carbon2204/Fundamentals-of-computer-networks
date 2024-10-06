import serial
import threading
import time
from tkinter import Tk, Label, Button, Entry, StringVar, Text, Scrollbar, END, OptionMenu, messagebox, Frame


# Функция для выбора направления
def update_ports_direction(*args):
    selected_direction = direction_var.get()
    port_mapping = {
        "1 -> 2": ("COM1", "COM2"),
        "5 <- 6": ("COM6", "COM5")
    }
    send_port, receive_port = port_mapping.get(selected_direction, ("COM1", "COM2"))
    send_var.set(send_port)
    receive_var.set(receive_port)


# Функция для посимвольной отправки данных
def send_data():
    message = entry_message.get()
    if message:
        try:
            sent_message = "".join(send_char(char) for char in message)
            update_state(len(sent_message))
            entry_message.set("")  
        except serial.SerialException as e:
            messagebox.showerror("Ошибка отправки", f"Ошибка при отправке данных: {e}")


def send_char(char):
    ser1.write(char.encode('utf-8'))  
    time.sleep(0.1)  
    return char


# Функция для чтения данных
def read_data():
    while True:
        try:
            if ser2.in_waiting > 0:
                received_data = ser2.read(1)
                display_received_data(received_data)
            time.sleep(0.1)
        except serial.SerialException as e:
            messagebox.showerror("Ошибка приёма", f"Ошибка при чтении данных: {e}")
            break


def display_received_data(received_data):
    try:
        decoded_char = received_data.decode('utf-8')
        text_output.insert(END, decoded_char)
    except UnicodeDecodeError:
        hex_data = received_data.hex()
        text_output.insert(END, f"[не декодировано: 0x{hex_data}]")
    text_output.see(END)


# Функция для обновления состояния (количество переданных байт и скорость порта)
def update_state(bytes_sent):
    global total_bytes
    total_bytes += bytes_sent
    state_label.config(text=f"Скорость: {ser1.baudrate} бод, Передано байт: {total_bytes}")


# Функция для запуска программы
def start_program():
    global ser1, ser2, total_bytes
    total_bytes = 0

    send_port = send_var.get()
    receive_port = receive_var.get()
    baudrate = int(baudrate_var.get())

    try:
        ser1 = serial.Serial(send_port, baudrate=baudrate, timeout=1)
        ser2 = serial.Serial(receive_port, baudrate=baudrate, timeout=1)

        threading.Thread(target=read_data, daemon=True).start()

        update_state(0)
    except serial.SerialException as e:
        messagebox.showerror("Ошибка порта", f"Не удалось открыть порт: {e}")


def close_ports():
    if 'ser1' in globals() and ser1.is_open:
        ser1.close()
    if 'ser2' in globals() and ser2.is_open:
        ser2.close()


# Создаем главное окно
root = Tk()
root.title("COM-порты: Передача и приём данных")
root.geometry("800x600")  
root.configure(bg="#0D1B2A")  
root.resizable(False, False)

# Верхний фрейм для настроек направления и скорости
frame_top = Frame(root, bg="#0D1B2A")
frame_top.pack(pady=20, padx=20, fill="x")

Label(frame_top, text="Выберите направление передачи данных:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
direction_var = StringVar(root)
direction_var.set("1 -> 2")
direction_var.trace("w", update_ports_direction)
direction_menu = OptionMenu(frame_top, direction_var, "1 -> 2", "5 <- 6")
direction_menu.grid(row=0, column=1, padx=5, pady=5)

Label(frame_top, text="Порт для отправки данных:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=1, column=0, sticky="w", pady=5)
send_var = StringVar(root)
send_label = Label(frame_top, textvariable=send_var, bg="#0D1B2A", fg="lightgray", font=("Arial", 12))
send_label.grid(row=1, column=1, padx=5, pady=5)

Label(frame_top, text="Порт для получения данных:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=2, column=0, sticky="w", pady=5)
receive_var = StringVar(root)
receive_label = Label(frame_top, textvariable=receive_var, bg="#0D1B2A", fg="lightgray", font=("Arial", 12))
receive_label.grid(row=2, column=1, padx=5, pady=5)

Label(frame_top, text="Выберите скорость передачи данных (бод):", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=3, column=0, sticky="w", pady=5)
baudrate_var = StringVar(root)
baudrate_var.set("9600")
baudrate_menu = OptionMenu(frame_top, baudrate_var, "9600", "19200", "38400", "57600", "115200")
baudrate_menu.grid(row=3, column=1, padx=5, pady=5)

# Средний фрейм для отправки сообщения
frame_middle = Frame(root, bg="#0D1B2A")
frame_middle.pack(pady=10, padx=20, fill="x")

Label(frame_middle, text="Введите сообщение для отправки:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
entry_message = StringVar()
message_entry = Entry(frame_middle, textvariable=entry_message, width=60)
message_entry.grid(row=1, column=0, padx=5, pady=5)

# Кнопка для отправки
send_button = Button(frame_middle, text="Отправить", command=send_data, bg="#2196F3", fg="white", padx=20, pady=5, font=("Arial", 12))
send_button.grid(row=1, column=1, padx=10)

# Нижний фрейм с двумя секциями для вывода данных и отладочной информации
frame_bottom = Frame(root, bg="#0D1B2A")
frame_bottom.pack(pady=10, padx=20, fill="x")

# Левая часть для вывода принятых данных
Label(frame_bottom, text="Принятые данные:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=0, column=0, sticky="w", pady=5)
text_output = Text(frame_bottom, height=10, width=40, bg="#333333", fg="white", insertbackground='white')
text_output.grid(row=1, column=0, padx=5, pady=5)

scrollbar = Scrollbar(frame_bottom, command=text_output.yview)
scrollbar.grid(row=1, column=1, sticky='ns')
text_output.config(yscrollcommand=scrollbar.set)

# Правая часть для отладочной информации
Label(frame_bottom, text="Отладочная информация:", bg="#0D1B2A", fg="lightgray", font=("Arial", 12)).grid(row=0, column=2, sticky="w", pady=5)
text_debug = Text(frame_bottom, height=10, width=40, bg="#333333", fg="white", insertbackground='white')
text_debug.grid(row=1, column=2, padx=5, pady=5)

scrollbar_debug = Scrollbar(frame_bottom, command=text_debug.yview)
scrollbar_debug.grid(row=1, column=3, sticky='ns')
text_debug.config(yscrollcommand=scrollbar_debug.set)

# Фрейм для состояния и кнопки запуска программы
frame_bottom_buttons = Frame(root, bg="#0D1B2A")
frame_bottom_buttons.pack(pady=20, padx=20, fill="x")

# Кнопка для запуска программы
start_button = Button(frame_bottom_buttons, text="Запустить", command=start_program, bg="#4CAF50", fg="white", padx=20, pady=5, font=("Arial", 12))
start_button.pack(side="left", padx=5)

# Окно для вывода состояния
state_label = Label(frame_bottom_buttons, text="Скорость: неизвестно, Передано байт: 0", bg="#0D1B2A", fg="lightgray", font=("Arial", 12))
state_label.pack(side="right")

# Завершение работы программы
root.protocol("WM_DELETE_WINDOW", lambda: [close_ports(), root.destroy()])
root.mainloop()
