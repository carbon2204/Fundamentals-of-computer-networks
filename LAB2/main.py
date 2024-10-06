import serial
import threading
import time
from tkinter import Tk, Label, Button, Entry, StringVar, Text, Scrollbar, END, OptionMenu, messagebox, Frame
from tkinter import font


n = 5  
FLAG = f"${chr(ord('a') + n)}"
DATA_LENGTH = n + 1
ESCAPE_BYTE = b'\x1b'
FLAG_BYTE = b'$'


def create_frame(data, source_port, dest_port):
    flag = FLAG.encode('utf-8')
    try:
        destination_address = int(dest_port[-1]).to_bytes(1, 'big')
    except ValueError:
        destination_address = b'\x00'  
    try:
        source_address = int(source_port[-1]).to_bytes(1, 'big')
    except ValueError:
        source_address = b'\x00'  
    fcs = b'\x00' * 4
    data_bytes = data.encode('utf-8').ljust(DATA_LENGTH, b'\x00')
    frame = flag + destination_address + source_address + data_bytes + fcs
    return byte_stuffing(frame)


def byte_stuffing(frame):
    stuffed_frame = frame.replace(ESCAPE_BYTE, ESCAPE_BYTE + ESCAPE_BYTE) 
    stuffed_frame = stuffed_frame.replace(FLAG_BYTE, ESCAPE_BYTE + FLAG_BYTE) 
    return stuffed_frame


def byte_destuffing(stuffed_frame):
    destuffed_frame = b''
    i = 0
    while i < len(stuffed_frame):
        if stuffed_frame[i:i+1] == ESCAPE_BYTE:
            if i + 1 < len(stuffed_frame):
                destuffed_frame += stuffed_frame[i + 1:i + 2]
                i += 2
            else:
                break  
        else:
            destuffed_frame += stuffed_frame[i:i+1]
            i += 1
    return destuffed_frame


def send_data():
    message = entry_message.get()
    if message:
        try:
            frame = create_frame(message, send_var.get(), receive_var.get())
            ser1.write(frame)
            update_state(len(frame))
            entry_message.set("") 
        except serial.SerialException as e:
            messagebox.showerror("Ошибка отправки", f"Ошибка при отправке данных: {e}")

def read_data():
    while True:
        try:
            if ser2.in_waiting > 0:
                received_frame = ser2.read(ser2.in_waiting)
                display_received_data(received_frame)
            time.sleep(0.1)
        except serial.SerialException as e:
            messagebox.showerror("Ошибка приёма", f"Ошибка при чтении данных: {e}")
            break

def display_received_data(received_frame):
    try:
        
        text_debug.insert(END, f"Принятые байты (до де-стаффинга): {received_frame.hex()}\n")
        text_debug.see(END)
        
        
        received_frame = byte_destuffing(received_frame)
        
        
        min_length = 4 + DATA_LENGTH
        if len(received_frame) < min_length:
            text_output.insert(END, f"[Ошибка: некорректная длина принятого кадра, минимальная длина {min_length}, получено {len(received_frame)}]\n")
            text_output.insert(END, f"Принятые байты: {received_frame.hex()}\n")
            text_output.see(END)
            return
        
        
        flag = received_frame[:2].decode('utf-8', errors='replace')
        dest_addr = int.from_bytes(received_frame[2:3], 'big')
        src_addr = int.from_bytes(received_frame[3:4], 'big')
        data = received_frame[4:4 + DATA_LENGTH].decode('utf-8', errors='replace').rstrip('\x00')
        fcs = received_frame[4 + DATA_LENGTH:].hex()
        
        text_output.insert(END, f"Flag: {flag}, Dest: {dest_addr}, Src: {src_addr}, Data: {data}, FCS: {fcs}\n")
        text_output.insert(END, f"Принятые байты: {received_frame.hex()}\n")
        text_output.see(END)
    except UnicodeDecodeError:
        text_output.insert(END, "[Ошибка декодирования данных]\n")
        text_output.see(END)


def update_state(bytes_sent):
    global total_bytes
    total_bytes += bytes_sent
    state_label.config(text=f"Скорость: {ser1.baudrate} бод, Передано байт: {total_bytes}")


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


def update_ports_direction():
    selected_direction = direction_var.get()
    if selected_direction == "1 -> 2":
        send_var.set("COM1")
        receive_var.set("COM2")
    elif selected_direction == "5 <- 6":
        send_var.set("COM6")
        receive_var.set("COM5")


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
