import tkinter as tk
from tkinter import ttk
import socket
import threading
import tkinter.messagebox as messagebox
import logging
import logging.handlers
import os
import keyboard
import requests
import re
import time
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

logging.basicConfig(filename='client.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

class SomeClass(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.socket = None
        self.connect_to_server()
        
        icon_path = resource_path("res/mipmap/Icon.ico")
        self.load_icon(icon_path)

class QueueClient:
    def __init__(self, master):
        self.master = master
        self.base_url = "http://localhost:5000"
        self.socket = None
        self.server_ip = "localhost"
        self.server_port = 5000
        self.connection_status_label = tk.Label(self.master, text="Disconnected", fg="red")
        self.connection_status_label.pack()
        self.reconnect_to_server()
        self.start_sync_threads()
        logging.info("Client application started")

log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)

log_file = os.path.join(log_directory, "client.log")
handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

for existing_handler in logger.handlers[:]:
    logger.removeHandler(existing_handler)

logger.addHandler(handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class ClientInterface(tk.Tk):
    def __init__(self):
        super().__init__()
        self.load_window_position()  
        self.title("Queuing System")
        self.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        self.geometry("700x600")  
        self.resizable(False, False)
        self.configure(bg="#F0F2F5")

        self.server_sync_thread = threading.Thread(target=self.sync_with_server, daemon=True)
        self.server_sync_thread.start()

        self.primary_color = "#2E3192" 
        self.secondary_color = "#FFC107" 
       
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('TLabel', background="#F0F2F5", foreground=self.primary_color, font=('Arial', 12))
        self.style.configure('TButton', background=self.primary_color, foreground='white', font=('Arial', 12, 'bold'))
        self.style.map('TButton', background=[('active', self.secondary_color)])

        self.status_indicator = tk.Canvas(self, width=20, height=20, bg=self['bg'], highlightthickness=0)
        self.status_indicator.place(x=10, y=10)
        self.status_circle = self.status_indicator.create_oval(2, 2, 18, 18, fill='red')

        self.create_interface()

        self.server_ip = self.load_server_ip()
        self.server_port = 58148
        self.socket = None
        self.connect_to_server()

        if not self.socket:
            messagebox.showerror("Connection Error", "Failed to connect to the Queuing Server. Please check the server IP and ensure the server is running.")
            self.after(0, self.prompt_server_ip)
        else:
            threading.Thread(target=self.listen_for_messages, daemon=True).start()
            self.initialize_system_ticket()
            self.request_current_exchange_rate()

        self.latest_system_ticket = "."
        self.latest_exchange_rate = "."
        
        self.start_sync_threads()

        self.bind("<Prior>", self.send_next_ticket)
        self.bind("<Next>", self.send_recall_ticket)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        logging.info("Client application started")

    def load_server_ip(self):
        try:
            with open("server_ip.txt", "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "127.0.0.1"

    def save_server_ip(self, ip):
        with open("server_ip.txt", "w") as f:
            f.write(ip)

    def prompt_server_ip(self):
        dialog = tk.Toplevel(self)
        dialog.title("Server IP Configuration")
        dialog.geometry("300x150")
        dialog.resizable(False, False)

        ttk.Label(dialog, text="Enter Server IP Address:").pack(pady=(20, 5))
        ip_entry = ttk.Entry(dialog, width=20)
        ip_entry.pack(pady=5)
        ip_entry.insert(0, self.server_ip)

        def update_ip():
            new_ip = ip_entry.get().strip()
            if new_ip:
                self.server_ip = new_ip
                self.save_server_ip(new_ip)
                self.connect_to_server()
                if self.socket:
                    messagebox.showinfo("Success", f"Connected to server at {new_ip}")
                    dialog.destroy()
                    self.after(0, self.start_listening)
                else:
                    messagebox.showerror("Connection Error", "Failed to connect to the server. Please check the IP and try again.")
            else:
                messagebox.showerror("Error", "Please enter a valid IP address.")

        ttk.Button(dialog, text="Connect", command=update_ip).pack(pady=10)

    def update_connection_status(self, is_connected):
        if is_connected:
            self.connection_status_label.config(text="Connected", fg="green")
        else:
            self.connection_status_label.config(text="Disconnected", fg="red")

    def check_server_connection(self):
        is_connected = self.check_connection()
        self.update_connection_status(is_connected)
        self.after(5000, self.check_server_connection)

    def prompt_password(self, event):
        dialog = tk.Toplevel(self)
        dialog.title("Enter Administrator Password")
        dialog.geometry("400x200")
        dialog.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        dialog.resizable(False, False)
        dialog.configure(bg="#F0F2F5")

        ttk.Label(dialog, text="Password:", font=("Arial", 12), background="#F0F2F5").pack(pady=(30, 5))

        password_entry = ttk.Entry(dialog, font=("Arial", 12), show="*")
        password_entry.pack(pady=5)
        password_entry.focus()

        def submit():
            password = password_entry.get()
            if password == "admin":
                self.open_settings()
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Incorrect password. Please try again.")

        ttk.Button(dialog, text="Submit", command=submit).pack(pady=(10, 5))

        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack(pady=(0, 10))

    def open_settings(self):
        settings_window = tk.Toplevel(self)
        settings_window.title("Settings")
        settings_window.geometry("300x200")
        settings_window.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        settings_window.configure(bg="#F0F2F5")

        ttk.Label(settings_window, text="Current IP: " + self.server_ip, font=("Arial", 12), background="#F0F2F5").pack(pady=(20, 5))

    def create_interface(self):
        header_frame = tk.Frame(self, bg=self.primary_color)
        header_frame.pack(fill=tk.X)
        header_label = tk.Label(header_frame, text="Queuing System", font=("Arial", 24, "bold"), fg="white", bg=self.primary_color)
        header_label.pack(side=tk.LEFT, padx=20, pady=10)

        header_label.bind("<Button-1>", self.prompt_password)

        yellow_line = tk.Frame(self, bg=self.secondary_color, height=5)
        yellow_line.pack(fill=tk.X)

        content_frame = tk.Frame(self, bg="#F0F2F5")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        left_frame = tk.Frame(content_frame, bg="#F0F2F5")
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        ttk.Label(left_frame, text="Select ticket letter:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
        letter_frame = tk.Frame(left_frame, bg="#F0F2F5")
        letter_frame.pack(anchor="w", pady=(0, 20))

        self.letter_var = tk.StringVar(value="")
        self.letter_buttons = {}
        for letter in ["A", "B", "C", "D", "E"]:
            button = tk.Button(letter_frame, text=letter,
                               font=("Arial", 12, "bold"),
                               bg="white", fg=self.primary_color,
                               activebackground=self.primary_color, activeforeground="white",
                               width=3, bd=1, relief="raised",
                               command=lambda l=letter: self.update_letter_selection(l))
            button.pack(side=tk.LEFT, padx=5)
            button.bind("<Enter>", lambda e, b=button: self.on_letter_hover(b))
            button.bind("<Leave>", lambda e, b=button: self.on_letter_leave(b))
            self.letter_buttons[letter] = button

        ttk.Label(left_frame, text="Select Teller:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 5))
        self.teller_var = tk.StringVar(value="")
        teller_options = [str(i) for i in range(1, 8)]
        self.teller_menu = ttk.Combobox(left_frame, textvariable=self.teller_var, values=teller_options,
                                        state="readonly", font=("Arial", 12), width=10)
        self.teller_menu.pack(fill=tk.X, pady=(0, 20))
        self.teller_menu.bind("<<ComboboxSelected>>", self.update_current_teller_selection)

        self.next_queue_button = tk.Button(left_frame, text="Next Queue", command=self.send_next_ticket,
                                           bg=self.primary_color, fg="white", font=("Arial", 16, "bold"),
                                           activebackground=self.secondary_color, activeforeground="black",
                                           height=2)
        self.next_queue_button.pack(fill=tk.X, pady=5)
        self.next_queue_button.bind("<Enter>", lambda e, b=self.next_queue_button: self.on_button_hover(b))
        self.next_queue_button.bind("<Leave>", lambda e, b=self.next_queue_button: self.on_button_leave(b))

        self.recall_ticket_button = tk.Button(left_frame, text="Recall Ticket", command=self.send_recall_ticket,
                                              bg=self.primary_color, fg="white", font=("Arial", 12, "bold"),
                                              activebackground=self.secondary_color, activeforeground="black")
        self.recall_ticket_button.pack(fill=tk.X, pady=5)
        self.recall_ticket_button.bind("<Enter>", lambda e, b=self.recall_ticket_button: self.on_button_hover(b))
        self.recall_ticket_button.bind("<Leave>", lambda e, b=self.recall_ticket_button: self.on_button_leave(b))

        reset_button = tk.Button(left_frame, text="Reset", command=self.clear_display,
                                 bg=self.primary_color, fg="white", font=("Arial", 12, "bold"),
                                 activebackground=self.secondary_color, activeforeground="black")
        reset_button.pack(fill=tk.X, pady=5)
        reset_button.bind("<Enter>", lambda e, b=reset_button: self.on_button_hover(b))
        reset_button.bind("<Leave>", lambda e, b=reset_button: self.on_button_leave(b))

        change_rate_button = tk.Button(left_frame, text="Update Exchange Rate", command=self.change_exchange_rate,
                                       bg=self.primary_color, fg="white", font=("Arial", 12, "bold"),
                                       activebackground=self.secondary_color, activeforeground="black")
        change_rate_button.pack(fill=tk.X, pady=5)
        change_rate_button.bind("<Enter>", lambda e, b=change_rate_button: self.on_button_hover(b))
        change_rate_button.bind("<Leave>", lambda e, b=change_rate_button: self.on_button_leave(b))

        custom_message_button = tk.Button(left_frame, text="Custom Message", command=self.send_custom_message,
                                          bg=self.primary_color, fg="white", font=("Arial", 12, "bold"),
                                          activebackground=self.secondary_color, activeforeground="black")
        custom_message_button.pack(fill=tk.X, pady=5)
        custom_message_button.bind("<Enter>", lambda e, b=custom_message_button: self.on_button_hover(b))
        custom_message_button.bind("<Leave>", lambda e, b=custom_message_button: self.on_button_leave(b))

        right_frame = tk.Frame(content_frame, bg="#F0F2F5")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_frame.pack_propagate(False)

        self.exchange_rate_label = ttk.Label(right_frame, text="Exchange Rate display: --", font=("Arial", 14))
        self.exchange_rate_label.place(x=50, y=160)

        self.current_teller_label = ttk.Label(right_frame, text="Current teller selection: --", font=("Arial", 14))
        self.current_teller_label.place(x=50, y=220)

        self.current_counter_ticket_label = ttk.Label(right_frame, text="Current counter ticket: --", font=("Arial", 14))
        self.current_counter_ticket_label.place(x=50, y=270)

        self.current_system_ticket_label = ttk.Label(right_frame, text="Current system ticket: --", font=("Arial", 14))
        self.current_system_ticket_label.place(x=50, y=320)

        footer_frame = tk.Frame(self, bg="#F0F2F5")
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)

        play_audio_button = tk.Button(footer_frame, text="Play Audio", command=self.show_audio_selection,
                                      bg=self.primary_color, fg="white", font=("Arial", 10, "bold"),
                                      activebackground=self.secondary_color, activeforeground="black")
        play_audio_button.pack(side=tk.LEFT, padx=10, pady=5)
        play_audio_button.bind("<Enter>", lambda e, b=play_audio_button: self.on_button_hover(b))
        play_audio_button.bind("<Leave>", lambda e, b=play_audio_button: self.on_button_leave(b))

        footer_label = tk.Label(footer_frame, text="Created by: Jhay EL", font=("Arial", 10),
                                fg=self.primary_color, bg="#F0F2F5")
        footer_label.pack(side=tk.RIGHT, padx=10, pady=5)

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            logging.info(f"Connected to the server at {self.server_ip}:{self.server_port}")
        except Exception as e:
            logging.error(f"Error connecting to server: {e}")
            self.socket = None

    def sync_with_server(self):
        while True:
            if self.socket:
                try:
                    self.request_system_ticket()
                    self.request_current_exchange_rate()
                    teller = self.teller_var.get()
                    if teller:
                        self.request_current_ticket()
                except Exception as e:
                    logging.error(f"Error syncing with server: {e}")
                    self.reconnect_to_server()
            else:
                self.reconnect_to_server()
            time.sleep(5)

    def reconnect_to_server(self):
        logging.info("Attempting to reconnect to the server...")
        self.connect_to_server()
        if self.socket:
            threading.Thread(target=self.listen_for_messages, daemon=True).start()

    def start_listening(self):
        threading.Thread(target=self.listen_for_messages, daemon=True).start()
        self.request_system_ticket()
        self.request_current_exchange_rate()

    def listen_for_messages(self):
        buffer = ''
        while True:
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    logging.info("Server disconnected.")
                    self.after(0, lambda: messagebox.showerror("Disconnected", "The server has disconnected."))
                    self.after(0, self.reset_display)
                    break
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    logging.info(f"Received message: {line}")
                    self.after(0, self.process_server_message, line)
            except Exception as e:
                logging.error(f"Error receiving message: {e}")
                self.after(0, lambda: messagebox.showerror("Error", "Lost connection to the server."))
                break
        self.after(0, self.reconnect_to_server)

    def process_server_message(self, message):
        try:
            command, value = message.split(':', 1)
            command_handlers = {
                'rate': self.update_exchange_rate,
                'ticket': self.handle_ticket_update,
                'system_ticket': self.update_system_ticket,
                'status_update': self.handle_status_update,
                'current_ticket': self.update_counter_ticket,
                'error': self.handle_error,
                'clear': lambda _: self.reset_display(),
                'exchange_rate': self.update_exchange_rate,
                'audio_played': self.handle_audio_played,
            }
            
            handler = command_handlers.get(command)
            if handler:
                self.after(0, lambda: handler(value))
                logging.info(f"Processed command: {command} with value: {value}")
            else:
                logging.warning(f"Unknown command received: {command}")
        except ValueError:
            logging.error(f"Invalid message format: {message}")
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def handle_audio_played(self, audio_name):
        logging.info(f"Audio played: {audio_name}")

    def update_counter_ticket(self, ticket):
        cleaned_ticket = self.clean_ticket_value(ticket)
        self.current_counter_ticket_label.config(text=f"Current counter ticket: {cleaned_ticket}")
        logging.info(f"Updated counter ticket to: {cleaned_ticket}")

    def update_system_ticket(self, ticket):
        if ticket != self.latest_system_ticket:
            self.latest_system_ticket = ticket
            self.current_system_ticket_label.config(text=f"Current system ticket: {ticket}")
            logging.info(f"Updated system ticket to: {ticket}")

    def handle_error(self, error_message):
        logging.error(f"Error: {error_message}")
        self.after(0, lambda: messagebox.showerror("Error", error_message))

    def reset_display(self):
        self.current_counter_ticket_label.config(text="Current counter ticket: --")
        self.current_system_ticket_label.config(text="Current system ticket: --")
        self.current_teller_label.config(text="Current teller selection: --")

    def handle_ticket_update(self, value):
        try:
            teller, ticket = value.split(',')
            self.update_current_ticket(teller, self.clean_ticket_value(ticket))
        except ValueError:
            logging.error(f"Invalid ticket update format: {value}")
            self.handle_error("Invalid ticket update received")

    def update_counter_ticket(self, ticket):
        cleaned_ticket = self.clean_ticket_value(ticket)
        self.current_counter_ticket_label.config(text=f"Current counter ticket: {cleaned_ticket}")
        logging.info(f"Updated counter ticket to: {cleaned_ticket}")

    def clean_ticket_value(self, value):
        cleaned = re.sub(r'^.*?:', '', value)
        cleaned = re.sub(r'[^A-Za-z0-9]', '', cleaned)
        return cleaned.strip()

    def start_sync_threads(self):
        threading.Thread(target=self.sync_with_server, daemon=True).start()

    def sync_with_server(self):
        while True:
            if self.socket:
                try:
                    self.request_system_ticket()
                    self.request_current_exchange_rate()
                    teller = self.teller_var.get()
                    if teller:
                        self.request_current_ticket()
                except Exception as e:
                    logging.error(f"Error syncing with server: {e}")
                    self.reconnect_to_server()
            else:
                self.reconnect_to_server()
            time.sleep(5)

    def request_system_ticket(self):
        if not self.socket:
            logging.error("No connection to server. Cannot request system ticket.")
            return

        try:
            self.socket.send("request_system_ticket:0\n".encode())
        except Exception as e:
            logging.error(f"Error requesting system ticket: {e}")

    def request_current_exchange_rate(self):
        if not self.socket:
            logging.error("No connection to server. Cannot request exchange rate.")
            return

        try:
            self.socket.send("request_exchange_rate:0".encode())
        except Exception as e:
            logging.error(f"Error requesting current exchange rate: {e}")

    def update_exchange_rate(self, rate):
        if rate != self.latest_exchange_rate:
            self.latest_exchange_rate = rate
            self.exchange_rate_label.config(text=f"Exchange Rate display: {rate}")
            logging.info(f"Updated exchange rate to: {rate}")

    def send_next_ticket(self, event=None):
        if not self.socket:
            logging.error("No connection to the server.")
            messagebox.showerror("Error", "No connection to the server. Attempting to reconnect...")
            self.reconnect_to_server()
            return
        teller = self.teller_var.get()
        letter = self.letter_var.get()
        if not teller or not letter:
            messagebox.showerror("Error", "Please select a Teller and Ticket Letter first")
            return
        
        self.next_queue_button.config(state=tk.DISABLED)

        message = f'next:{teller},{letter}'
        try:
            self.socket.send(message.encode())
            self.current_teller_label.config(text=f"Current teller selection: TELLER NO. {teller}")
            logging.info(f"Sent next ticket request: {message}")
        except Exception as e:
            logging.error(f"Error sending message: {e}")
            messagebox.showerror("Error", f"Failed to send message: {str(e)}")
            self.reconnect_to_server()
        finally:
            self.after(1000, lambda: self.next_queue_button.config(state=tk.NORMAL))

    def reconnect_to_server(self):
        logging.info("Attempting to reconnect to the server...")
        try:
            if self.socket:
                self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip, self.server_port))
            logging.info("Reconnected to the server successfully.")
            self.update_connection_status(True)
            threading.Thread(target=self.listen_for_messages, daemon=True).start()
        except Exception as e:
            logging.error(f"Error reconnecting to server: {e}")
            self.update_connection_status(False)
            self.socket = None
            self.after(5000, self.reconnect_to_server)

    def send_recall_ticket(self, event=None):
        teller = self.teller_var.get()
        if not teller:
            messagebox.showerror("Error", "Please select a Teller first")
            return
        message = f'recall:{teller}'
        try:
            self.socket.send(message.encode())
            logging.info(f"Recall ticket requested by Teller {teller}")
        except Exception as e:
            logging.error(f"Error sending recall ticket request: {e}")
            messagebox.showerror("Error", "Failed to recall ticket. Please try again.")

    def clear_display(self):
        if not self.socket:
            logging.error("No connection to the server.")
            return
        confirmation = messagebox.askyesno("Clear Data", "This will remove all the data on the Queue Server, do you want to continue?")
        if confirmation:
            message = 'clear:0'
            try:
                self.socket.send(message.encode())
                response = self.socket.recv(1024).decode()
                if response == "clear:acknowledged":
                    self.reset_display()
                else:
                    logging.error(f"Unexpected response from server: {response}")
            except Exception as e:
                logging.error(f"Error sending clear message: {e}")
                messagebox.showerror("Error", "Failed to clear data. Please try again.")

    def change_exchange_rate(self):
        if not self.socket:
            logging.error("No connection to the server.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Update Exchange Rate")
        dialog.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        dialog.configure(bg="#F0F2F5")

        ttk.Label(dialog, text="Enter new exchange rate:", font=("Arial", 12), background="#F0F2F5").pack(pady=(20, 10))

        rate_entry = ttk.Entry(dialog, font=("Arial", 12), width=20)
        rate_entry.pack(pady=10)
        rate_entry.focus()

        def submit():
            rate = rate_entry.get()
            if rate:
                if messagebox.askyesno("Confirmation", "Do you want to change the Exchange rate on the Queuing Server?"):
                    message = f'rate:{rate}'
                    try:
                        self.socket.send(message.encode())
                        messagebox.showinfo("Success", "Rate Updated!")
                        dialog.destroy()
                    except Exception as e:
                        logging.error(f"Error sending message: {e}")
                        messagebox.showerror("Error", "Failed to update rate. Please try again.")
            else:
                messagebox.showerror("Error", "Please enter a valid rate.")

        ttk.Button(dialog, text="Update", command=submit,
                   style='TButton').pack(pady=10)

    def send_custom_message(self):
        if not self.socket:
            logging.error("No connection to the server.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Custom Message")
        dialog.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.configure(bg="#F0F2F5")

        ttk.Label(dialog, text="Duration of the message (seconds):", font=("Arial", 12), background="#F0F2F5").pack(pady=(20, 5))
        duration_entry = ttk.Entry(dialog, font=("Arial", 12), width=20)
        duration_entry.pack(pady=5)
        duration_entry.focus()

        ttk.Label(dialog, text="Enter Custom Message (max 100 characters):", font=("Arial", 12), background="#F0F2F5").pack(pady=(10, 5))
        message_entry = tk.Text(dialog, font=("Arial", 12), width=40, height=5)
        message_entry.pack(pady=5)

        def send_message():
            duration = duration_entry.get()
            message_text = message_entry.get("1.0", "end").strip()
            if not duration.isdigit() or int(duration) <= 0:
                messagebox.showerror("Error", "Please enter a valid duration in seconds.")
                return
            if len(message_text) == 0 or len(message_text) > 100:
                messagebox.showerror("Error", "Message must be between 1 and 100 characters.")
                return
            if messagebox.askyesno("Confirmation", "Do you want to send this message to the server display?"):
                message = f'custom_message:{duration}:{message_text}'
                try:
                    self.socket.send(message.encode())
                    messagebox.showinfo("Success", "Message sent!")
                    dialog.destroy()
                except Exception as e:
                    logging.error(f"Error sending custom message: {e}")
                    messagebox.showerror("Error", "Failed to send message. Please try again.")

        ttk.Button(dialog, text="Send Message", command=send_message,
                   style='TButton').pack(pady=10)

    def show_audio_selection(self):
        audio_window = tk.Toplevel(self)
        audio_window.title("Select Audio")
        audio_window.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        audio_window.geometry("320x320")
        audio_window.resizable(False, False)
        audio_window.configure(bg="#F0F2F5")

        button_width = 25

        tk.Button(audio_window, text="Queue Sound", command=self.play_queue_sound,
                  bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)
        
        tk.Button(audio_window, text="Birthday Song - ENG", command=self.play_hbd_song,
                  bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

        tk.Button(audio_window, text="Birthday Song - TAG", command=self.play_maligayang_bati,
                  bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

        tk.Button(audio_window, text="Birthday Song - ITA", command=self.play_buon_compleanno,
                  bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

        tk.Button(audio_window, text="Congratulations", command=self.play_congratulations,
                  bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

        tk.Button(audio_window, text="Clap", command=self.play_clap, bg=self.primary_color, fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

        tk.Button(audio_window, text="Stop Music", command=self.stop_music,
                  bg="red", fg="white", font=("Arial", 12, "bold"), width=button_width).pack(pady=5)

    def play_queue_sound(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/Queueing Sound.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play audio command: {e}")
                messagebox.showerror("Error", "Failed to play queue sound. Please try again.")

    def play_hbd_song(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/HBD Song.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play HBD song command: {e}")
                messagebox.showerror("Error", "Failed to play Happy Birthday song. Please try again.")

    def play_maligayang_bati(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/maligayang-bati.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play Maligayang Bati command: {e}")
                messagebox.showerror("Error", "Failed to play Maligayang Bati. Please try again.")

    def play_buon_compleanno(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/buon-compleanno.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play Buon Compleano command: {e}")
                messagebox.showerror("Error", "Failed to play Buon Comp leano. Please try again.")

    def play_congratulations(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/congratulations.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play Congratulations command: {e}")
                messagebox.showerror("Error", "Failed to play Congratulations. Please try again.")

    def play_clap(self):
        if self.socket:
            try:
                self.socket.send(f"play_audio:{resource_path('res/sounds/clapping.mp3')}".encode())
            except Exception as e:
                logging.error(f"Error sending play Clap command: {e}")
                messagebox.showerror("Error", "Failed to play Clap. Please try again.")

    def stop_music(self):
        if self.socket:
            try:
                self.socket.send("stop_audio".encode())
                response = self.socket.recv(1024).decode().strip()
                if response == "audio_stopped":
                    logging.info("Music stopped successfully")
                    messagebox.showinfo("Success", "Music stopped successfully")
                else:
                    logging.info(f"Received response from server: {response}")
                    messagebox.showinfo("Info", "Music stop command sent to server")
            except Exception as e:
                logging.error(f"Error stopping music: {e}")
                messagebox.showerror("Error", f"Failed to stop music: {str(e)}")
        else:
            logging.error("No connection to server. Cannot stop music.")
            messagebox.showerror("Error", "No connection to server. Cannot stop music.")

    def update_current_ticket(self, teller, ticket):
        if teller == self.teller_var.get():
            clean_ticket = ticket.split('current ticket')[-1].strip()
            self.current_counter_ticket_label.config(text=f"Current counter ticket: {clean_ticket}")
        else:
            try:
                self.socket.send(f"status_request:{self.teller_var.get()}".encode())
            except Exception as e:
                logging.error(f"Error requesting current ticket for new teller: {e}")

    def update_current_teller_selection(self, _=None):
        teller = self.teller_var.get()
        self.current_teller_label.config(text=f"Current teller selection: TELLER NO. {teller}")
        if teller:
            self.request_current_ticket()
            self.update_counter_ticket(".")

    def handle_status_update(self, value):
        pass

    def request_current_ticket(self):
        teller = self.teller_var.get()
        if teller:
            try:
                self.socket.send(f"status_request:{teller}\n".encode())
            except Exception as e:
                logging.error(f"Error requesting current ticket: {e}")

    def update_letter_selection(self, selected_letter):
        self.letter_var.set(selected_letter)
        for letter, button in self.letter_buttons.items():
            if letter == selected_letter:
                button.config(bg=self.primary_color, fg="white")
            else:
                button.config(bg="white", fg=self.primary_color)

    def on_letter_hover(self, button):
        if button['text'] != self.letter_var.get():
            button.config(bg=self.primary_color, fg="white")

    def on_letter_leave(self, button):
        if button['text'] != self.letter_var.get():
            button.config(bg="white", fg=self.primary_color)

    def on_button_hover(self, button):
        button.config(bg=self.secondary_color, fg="black")

    def on_button_leave(self, button):
        button.config(bg=self.primary_color, fg="white")

    def on_closing(self):
        self.save_window_position()
        try:
            keyboard.remove_hotkey('page up')
            keyboard.remove_hotkey('page down')
        except KeyError:
            pass
        self.destroy()

    def show_error(self, message):
        threading.Thread(target=lambda: messagebox.showerror("Error", message)).start()

    def update_date_label(self):
        current_date = self.server.get_current_date()
        font_size = self.server.get_date_font_size()
        
        adjusted_font_size = int(font_size * 1.2)
        date_font = ("Arial", adjusted_font_size, "bold")
        
        self.date_label.config(
            text=f"As of {current_date}",
            font=date_font,
            pady=10
        )
        self.after(1000, self.update_date_label)

    def save_window_position(self):
        position = f"{self.winfo_x()}+{self.winfo_y()}"
        with open("client_window_position.txt", "w") as f:
            f.write(position)

    def load_window_position(self):
        try:
            with open("client_window_position.txt", "r") as f:
                position = f.read().strip()
                self.geometry(f"+{position}")
        except FileNotFoundError:
            pass

    def initialize_system_ticket(self):
        pass

    def check_client_connections(self):
        with self.clients_lock:
            disconnected_clients = []
            for client in self.clients:
                try:
                    client.send("ping\n".encode())
                except Exception as e:
                    logging.error(f"Client disconnected: {e}")
                    disconnected_clients.append(client)
            
            for client in disconnected_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
                logging.info(f"Removed disconnected client: {client}")
        
        self.after(60000, self.check_client_connections)

    def send_request(self, data):
        try:
            response = requests.post(f"{self.base_url}/api", json=data)
            response.raise_for_status()
            logging.info(f"Request sent successfully: {data}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending request: {str(e)}")
            return None

    def load_icon(self, path):
        if os.path.exists(path):
            self.iconbitmap(path)
        else:
            logging.error(f"Icon file not found: {path}")
            messagebox.showerror("Error", "Icon file not found.")

if __name__ == "__main__":
    client_interface = ClientInterface()
    client_interface.mainloop()
    logging.info("Client started")