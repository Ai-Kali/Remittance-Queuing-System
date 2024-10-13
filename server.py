import tkinter as tk
from tkinter import messagebox
import socket
import threading
import os
import logging
import pygame
import time
import sys

logging.basicConfig(filename="server.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class ServerInterface(tk.Tk):
    def __init__(self):
        super().__init__()
        self.load_window_position()
        self.setup_window()
        self.create_widgets()
        self.initialize_variables()
        self.setup_audio()
        self.start_server_thread()
        self.latest_system_ticket = "--"
        self.current_exchange_rate = "00.00"
        self.is_playing_audio = False
        self.after(60000, self.check_client_connections)
        self.fullscreen = False
        self.top_bar_click_count = 0
        self.top_bar.bind("<Button-1>", self.on_top_bar_click)
        self.bind("<Escape>", self.exit_fullscreen)  # Add this line

    def setup_window(self):
        self.title("Queuing System - Server")
        self.iconbitmap(resource_path("res/mipmap/Icon.ico"))
        self.geometry("360x640")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Configure>", self.on_resize)
        self.bind("<Button-3>", self.right_click)

    def create_widgets(self):
        self.create_top_bar()
        self.create_middle_frame()
        self.create_bottom_bar()
        self.create_date_label()

    def create_top_bar(self):
        self.top_bar = tk.Frame(self, bg="#2e3192")
        self.top_bar.pack(side=tk.TOP, fill=tk.X)
        
        self.ticket_no_label = tk.Label(self.top_bar, text="TICKET NO.", bg="#2e3192", fg="white")
        self.ticket_no_label.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        self.teller_label = tk.Label(self.top_bar, text="TELLER", bg="#2e3192", fg="white")
        self.teller_label.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)

    def create_middle_frame(self):
        self.middle_frame = tk.Frame(self)
        self.middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.middle_frame.grid_columnconfigure(0, weight=1)
        for i in range(1, 8):
            self.middle_frame.grid_rowconfigure(i, weight=1)

        self.ticket_labels = {}
        self.teller_numbers = {}
        self.teller_frames = {}

        for teller in range(1, 8):
            teller_frame = tk.Frame(self.middle_frame)
            teller_frame.grid(row=teller, column=0, sticky="nsew")
            self.teller_frames[teller] = teller_frame

            teller_frame.grid_columnconfigure(0, weight=1)
            teller_frame.grid_columnconfigure(1, weight=1)
            teller_frame.grid_rowconfigure(0, weight=1)

            ticket_frame = tk.Frame(teller_frame, width=180)
            ticket_frame.grid(row=0, column=0, sticky="nsew")
            ticket_frame.grid_propagate(False)
            ticket_frame.grid_columnconfigure(0, weight=1)
            ticket_frame.grid_rowconfigure(0, weight=1)

            ticket_label = tk.Label(ticket_frame, text=".", anchor='center')
            ticket_label.grid(row=0, column=0, sticky="nsew")
            self.ticket_labels[teller] = ticket_label

            teller_frame = tk.Frame(teller_frame, width=180)
            teller_frame.grid(row=0, column=1, sticky="nsew")
            teller_frame.grid_propagate(False)
            teller_frame.grid_columnconfigure(0, weight=1)
            teller_frame.grid_rowconfigure(0, weight=1)

            teller_number_label = tk.Label(teller_frame, text=f"{teller}", anchor='center')
            teller_number_label.grid(row=0, column=0, sticky="nsew")
            self.teller_numbers[teller] = teller_number_label

    def create_bottom_bar(self):
        self.bottom_bar = tk.Frame(self, bg="#2e3192")
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_bar.grid_columnconfigure(0, weight=1)
        self.bottom_bar.grid_rowconfigure(0, weight=150)  
        for i in range(1, 20):
            self.bottom_bar.grid_rowconfigure(i, weight=2)
            self.bottom_bar.grid_columnconfigure(i, weight=0)

        self.create_date_label()

        self.exchange_rate_label = tk.Label(self.bottom_bar, text="E X C H A N G E  R A T E", bg="#2e3192", fg="white")
        self.exchange_rate_label.grid(row=2, column=0)

        self.currency_label = tk.Label(self.bottom_bar, text="E u r o  t o  P h i l i p p i n e  P e s o", bg="#2e3192", fg="white")
        self.currency_label.grid(row=3, column=0)

        self.exchange_rate_value_label = tk.Label(self.bottom_bar, text="₱00.00", bg="#2e3192", fg="white")
        self.exchange_rate_value_label.grid(row=4, column=0)

        self.disclaimer_label = tk.Label(
            self.bottom_bar,
            text="Disclaimer: Changes in our exchange rate may be applied immediately and without prior notice.",
            fg="#c9c9c9",
            bg="#2e3192",
            wraplength=280
        )
        self.disclaimer_label.grid(row=5, column=0, pady=2, sticky="s")

    def create_date_label(self):
        self.date_label = tk.Label(self.bottom_bar, bg="#2e3192", fg="white", anchor="center")
        self.date_label.grid(row=1, column=0, sticky="ew", padx=10, pady=2)
        self.update_date_label()

    def update_date_label(self):
        width = self.winfo_width()
        base_size = width // 40
        date_font = ("Arial", base_size)

        current_date = time.strftime("%B %d, %Y %I:%M %p", time.localtime())
        if hasattr(self, 'date_label'):
            self.date_label.config(text=current_date, font=date_font)
        else:
            logging.error("date_label is not initialized.")
        self.after(1000, self.update_date_label)

    def get_current_date(self):
        return time.strftime("%B %d, %Y %I:%M %p", time.localtime())

    def get_date_font_size(self):
        width, height = self.winfo_width(), self.winfo_height()
        return min(width // 25, height // 35)

    def initialize_variables(self):
        self.ticket_data = {letter: 0 for letter in "ABCDE"}
        self.latest_system_ticket = "."
        self.last_tickets = {teller: "." for teller in range(1, 8)}
        self.previous_tickets = {teller: [] for teller in range(1, 8)}
        self.clients = []
        self.clients_lock = threading.Lock()
        self.flash_steps = 10
        self.flash_duration = 2500
        self.flash_color = "#FFFF00"
        self.flash_queue = {}
        self.is_flashing = {}
        self.right_click_count = 0

    def setup_audio(self):
        pygame.mixer.init()
        self.sound_file = resource_path("res/sounds/Queueing Sound.mp3")
        self.hbd_song_file = resource_path("res/sounds/HBD Song.mp3")
        self.announcement_audio_file = resource_path("res/sounds/announcement.mp3")
        
        for file in [self.sound_file, self.hbd_song_file, self.announcement_audio_file]:
            if not os.path.exists(file):
                logging.error(f"Audio file not found: {file}")
                messagebox.showerror("Error", f"Audio file not found: {file}")

        try:
            self.queue_sound = pygame.mixer.Sound(self.sound_file)
            self.hbd_sound = pygame.mixer.Sound(self.hbd_song_file)
        except pygame.error as e:
            logging.error(f"Error loading sound files: {e}")
            messagebox.showerror("Error", f"Error loading sound files: {e}")

    def start_server_thread(self):
        threading.Thread(target=self.start_server, daemon=True).start()

    def update_font_sizes(self):
        width, height = self.winfo_width(), self.winfo_height()
        base_size = min(width // 16, height // 26)

        self.bold_font = ("Arial", base_size, "bold")
        self.bold_font_small = ("Arial", int(base_size * 0.9), "bold")
        self.small_font = ("Arial", int(base_size * 0.5))
        self.disclaimer_font = ("Arial", int(base_size * 0.3))
        self.rate_value_label_fomt = ("Arial", int(base_size * 1.8), "bold")
        self.date_font = ("Arial", int(base_size * 0.5)) 

        self.update_widget_fonts()

    def update_widget_fonts(self):
        self.ticket_no_label.config(font=self.bold_font_small)
        self.teller_label.config(font=self.bold_font_small)
        self.exchange_rate_label.config(font=self.bold_font_small)
        self.currency_label.config(font=self.small_font)
        self.exchange_rate_value_label.config(fg='#ffce00', font=self.rate_value_label_fomt)
        self.disclaimer_label.config(font=self.disclaimer_font)
        self.date_label.config(font=self.date_font) 

        for label in self.ticket_labels.values():
            label.config(font=self.bold_font)
        for label in self.teller_numbers.values():
            label.config(font=self.bold_font)

    def on_resize(self, event):
        self.update_font_sizes()
        self.disclaimer_label.config(wraplength=self.winfo_width() - 20)
        total_height = self.winfo_height()
        self.top_bar.config(height=total_height // 12)
        self.bottom_bar.config(height=total_height // 4)
        self.update_date_label()

    def update_display(self, teller, ticket):
        if teller in self.ticket_labels:
            self.after(0, self._update_display_gui, teller, ticket)
            self.latest_system_ticket = ticket
            self.last_tickets[teller] = ticket
            self.play_sound()
            self.broadcast(f'ticket:{teller},{ticket}')
            self.broadcast(f'system_ticket:{self.latest_system_ticket}')
            
            if teller not in self.flash_queue:
                self.flash_queue[teller] = []
            self.flash_queue[teller].append(2)
            
            if not self.is_flashing.get(teller, False):
                self.start_flash_sequence(teller)

    def _update_display_gui(self, teller, ticket):
        self.ticket_labels[teller].config(text=ticket)
        self.teller_numbers[teller].config(text=f"{teller}")

    def start_flash_sequence(self, teller):
        if self.flash_queue[teller]:
            flash_count = self.flash_queue[teller].pop(0)
            self.is_flashing[teller] = True
            self.flash_label(teller, self.teller_frames[teller], 0, flash_count)
        else:
            self.is_flashing[teller] = False

    def flash_label(self, teller, widget, step, remaining_flashes):
        if remaining_flashes > 0:
            if step < self.flash_steps * 2:
                ratio = step / self.flash_steps if step < self.flash_steps else (2 * self.flash_steps - step) / self.flash_steps
                new_color = self.interpolate_color(self.cget("bg"), self.flash_color, ratio)
                self.update_teller_colors(teller, new_color)
                self.after(self.flash_duration // (6 * self.flash_steps), 
                           lambda: self.flash_label(teller, widget, step + 1, remaining_flashes))
            else:
                self.flash_label(teller, widget, 0, remaining_flashes - 1)
        else:
            self.update_teller_colors(teller, self.cget("bg"))
            self.start_flash_sequence(teller)

    def update_teller_colors(self, teller, color):
        self.teller_frames[teller].config(bg=color)
        self.ticket_labels[teller].config(bg=color, anchor='center')
        self.teller_numbers[teller].config(bg=color)

    def interpolate_color(self, color1, color2, ratio):
        r1, g1, b1 = self.winfo_rgb(color1)
        r2, g2, b2 = self.winfo_rgb(color2)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f'#{r//256:02x}{g//256:02x}{b//256:02x}'

    def update_exchange_rate(self, rate):
        self.current_exchange_rate = rate
        formatted_rate = f"₱{rate}"
        self.after(0, self._update_exchange_rate_gui, formatted_rate)
        self.broadcast(f'rate:{formatted_rate}')
        self.play_audio("C:\\GitHub Projects\\Remittance-Queuing-System\\res\\sounds\\erupdated.mp3")

    def _update_exchange_rate_gui(self, formatted_rate):
        self.exchange_rate_value_label.config(text=formatted_rate)

    def clear_data(self):
        logging.info("Initiating clear data operation.")
        self.ticket_data = {letter: 0 for letter in "ABCDE"}
        self.latest_system_ticket = "."
        self.last_tickets = {teller: "." for teller in range(1, 8)}
        self.previous_tickets = {teller: [] for teller in range(1, 8)}

        for teller in self.ticket_labels:
            self.ticket_labels[teller].config(text="-", bg=self.cget("bg"))
            self.teller_numbers[teller].config(bg=self.cget("bg"))
            self.teller_frames[teller].config(bg=self.cget("bg"))

        self.broadcast("clear:0")
        logging.info("Broadcasted clear command to all clients.")
        self.play_sound()

    def manual_entry(self, teller, letter, ticket_number):
        self.ticket_data[letter] = int(ticket_number) - 1
        manual_ticket = f"{letter}{ticket_number:03d}"
        self.update_display(teller, manual_ticket)

    def broadcast(self, message):
        with self.clients_lock:
            disconnected_clients = []
            for client in self.clients:
                try:
                    client.send(f"{message}\n".encode())
                except Exception as e:
                    logging.error(f"Error sending to client: {e}")
                    disconnected_clients.append(client)
            for client in disconnected_clients:
                self.clients.remove(client)
                try:
                    client.close()
                except:
                    pass
                logging.info(f"Removed disconnected client: {client}")

    def start_server(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind(('0.0.0.0', 58148))
            server_socket.listen(5)
            print("Server is listening on port 58148")
            logging.info("Server started and listening for connections...")

            while True:
                client_socket, addr = server_socket.accept()
                with self.clients_lock:
                    self.clients.append(client_socket)
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
        except Exception as e:
            logging.error(f"Error in server: {e}")

    def handle_client(self, client_socket):
        try:
            while True:
                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        logging.info("Client disconnected.")
                        break
                    logging.info(f"Received data: {data}")
                    
                    command = data.strip()
                    
                    if command == "request_system_data":
                        self.send_system_data(client_socket)
                    else:
                        self.process_client_data(data, client_socket)
                except ConnectionResetError:
                    logging.error("Connection reset by client.")
                    break
                except Exception as e:
                    logging.error(f"Error receiving data from client: {e}")
                    break
        except Exception as e:
            logging.error(f"Error handling client: {e}")
        finally:
            with self.clients_lock:
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
            client_socket.close()
            logging.info("Client disconnected and socket closed.")

    def process_client_data(self, data, client_socket):
        try:
            if data.startswith('custom_message:'):
                self.handle_custom_message(data)
            elif data.startswith('play_audio:'):
                self.handle_play_audio(data, client_socket)
            elif data.startswith('stop_audio'):
                self.stop_audio()
                client_socket.send("audio_stopped\n".encode())
            else:
                command, value = data.split(':', 1)
                if command == 'next':
                    self.handle_next_ticket(value, client_socket)
                elif command == 'recall':
                    self.handle_recall_ticket(value, client_socket)
                elif command == 'manual':
                    self.handle_manual_entry(value)
                elif command == 'clear':
                    self.clear_data()
                    client_socket.send("clear:acknowledged\n".encode())
                elif command == 'rate':
                    self.update_exchange_rate(value)
                elif command == 'status_request':
                    self.handle_status_request(value, client_socket)
                elif command == 'request_system_ticket':
                    client_socket.send(f"system_ticket:{self.latest_system_ticket}\n".encode())
                elif command == 'request_exchange_rate':
                    client_socket.send(f"exchange_rate:{self.current_exchange_rate}\n".encode())
        except Exception as e:
            logging.error(f"Error processing client data: {e}")

    def handle_custom_message(self, data):
        parts = data.split(':', 2)
        if len(parts) == 3:
            duration = int(parts[1])
            message_text = parts[2]
            self.broadcast(f"custom_message:{duration}:{message_text}")
            self.after(0, self.display_custom_message, message_text, duration)
            self.play_audio(self.announcement_audio_file)
        return "custom_message:sent\n"

    def handle_play_audio(self, data, client_socket):
        audio_path = data.split(':', 1)[1]
        audio_name = os.path.basename(audio_path)
        self.play_audio(audio_path)
        client_socket.send(f"audio_played:{audio_name}\n".encode())

    def handle_next_ticket(self, value, client_socket):
        teller, letter = value.split(',')
        self.ticket_data[letter] += 1
        ticket_number = f"{letter}{self.ticket_data[letter]:03d}"
        if int(teller) in self.last_tickets and self.last_tickets[int(teller)] != '-':
            self.previous_tickets[int(teller)].append(self.last_tickets[int(teller)])
        self.update_display(int(teller), ticket_number)
        self.latest_system_ticket = ticket_number
        client_socket.send(f'current_ticket:{ticket_number}\n'.encode())
        client_socket.send(f'system_ticket:{ticket_number}\n'.encode())

    def handle_recall_ticket(self, value, client_socket):
        teller = int(value)
        current_ticket = self.last_tickets.get(teller)
        if current_ticket and current_ticket != '.':
            self.update_display(teller, current_ticket)
            self.latest_system_ticket = current_ticket
            client_socket.send(f'current_ticket:{current_ticket}\n'.encode())
            client_socket.send(f'system_ticket:{current_ticket}\n'.encode())
            self.broadcast(f"ticket:{teller},{current_ticket}")
        else:
            client_socket.send('error:No current ticket to recall\n'.encode())

    def handle_manual_entry(self, value):
        teller, letter, ticket_number = value.split(',')
        self.manual_entry(int(teller), letter, ticket_number)

    def handle_status_request(self, value, client_socket):
        teller_number = int(value)
        last_ticket = self.last_tickets.get(teller_number, ".")
        client_socket.send(f"current_ticket:{last_ticket}\n".encode())

    def play_audio(self, audio_path):
        try:
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            self.is_playing_audio = True
            logging.info(f"Playing audio: {audio_path}")
        except Exception as e:
            logging.error(f"Error playing audio {audio_path}: {e}")
    def display_custom_message(self, message_text, duration):
        logging.info(f"Displaying custom message: {message_text} for {duration} seconds")
        custom_window = tk.Toplevel(self)
        custom_window.overrideredirect(True)
        
        # Get the screen width and height
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Set the window to full screen
        custom_window.geometry(f"{screen_width}x{screen_height}+0+0")
        
        bg_color, text_color = 'white', '#2e3192'
        custom_window.configure(bg=bg_color)

        message_label = tk.Label(custom_window, text=message_text, fg=text_color, bg=bg_color, 
                                 wraplength=screen_width - 40)
        message_label.pack(expand=True)

        font_size = 100
        while font_size > 10:
            message_label.config(font=("Arial", font_size, "bold"))
            custom_window.update_idletasks()
            if message_label.winfo_reqheight() <= screen_height - 40 and message_label.winfo_reqwidth() <= screen_width - 40:
                break
            font_size -= 2

        custom_window.after(duration * 1000, custom_window.destroy)
        custom_window.lift()
        custom_window.attributes('-topmost', True)
        custom_window.attributes('-fullscreen', True)
        custom_window.after_idle(custom_window.attributes, '-topmost', False)

    def play_sound(self):
        try:
            self.queue_sound.play()
            logging.info("Queue sound played successfully.")
        except Exception as e:
            logging.error(f"Error playing queue sound: {e}")

    def play_hbd_song(self):
        try:
            self.hbd_sound.play()
            logging.info("Happy Birthday song played successfully.")
        except Exception as e:
            logging.error(f"Error playing Happy Birthday song: {e}")

    def get_previous_ticket(self, teller):
        if teller in self.previous_tickets and self.previous_tickets[teller]:
            previous_ticket = self.previous_tickets[teller].pop()
            if previous_ticket:
                self.last_tickets[teller] = previous_ticket
                return previous_ticket
        return None

    def on_closing(self):
        self.save_window_position()
        pygame.mixer.quit()
        self.destroy()

    def confirm_close(self):
        if messagebox.askokcancel("Quit", "Do you really want to quit?"):
            self.on_closing()

    def right_click(self, event):
        self.right_click_count += 1
        if self.right_click_count == 3:
            self.confirm_close()
            self.right_click_count = 0
        else:
            self.after(500, self.reset_click_count)

    def reset_click_count(self):
        self.right_click_count = 0

    def update_date_label(self):
        current_date = time.strftime("%B %d, %Y %I:%M %p", time.localtime())
        if hasattr(self, 'date_label'):
            self.date_label.config(text=current_date)
        else:
            logging.error("date_label is not initialized.")
        self.after(1000, self.update_date_label)

    def get_current_date(self):
        return time.strftime("%B %d, %Y %I:%M %p", time.localtime())

    def get_date_font_size(self):
        width, height = self.winfo_width(), self.winfo_height()
        return max(20, min(width // 25, height // 35))

    def save_window_position(self):
        position = f"{self.winfo_x()}+{self.winfo_y()}"
        with open("window_position.txt", "w") as f:
            f.write(position)

    def load_window_position(self):
        try:
            with open("window_position.txt", "r") as file:
                position = file.read().strip()
                if 'x' in position:
                    width, height = position.split('x')
                    self.geometry(f"{width}x{height}")
                else:
                    x, y = map(int, position.split('+')[1:])
                    self.geometry(f"+{x}+{y}")
        except (FileNotFoundError, ValueError, IndexError):
            self.geometry("800x600+100+100")

    def handle_client_message(self, client_socket, message):
        data = client_socket.recv(1024).decode('utf-8')
        command = data.strip()
        if command == "request_system_data":
            self.send_system_data(client_socket)

    def send_system_data(self, client_socket):
        system_data = {
            'system_ticket': self.latest_system_ticket,
            'exchange_rate': self.current_exchange_rate
        }
        message = f"system_data:{system_data}\n"
        client_socket.send(message.encode())

    def broadcast_system_update(self):
        system_data = {
            'system_ticket': self.latest_system_ticket,
            'exchange_rate': self.current_exchange_rate
        }
        message = f"system_data:{system_data}\n"
        self.broadcast(message)

    def stop_audio(self):
        if self.is_playing_audio:
            pygame.mixer.music.stop()
            self.is_playing_audio = False
            logging.info("Audio stopped")
        else:
            logging.info("No audio playing to stop")

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

    def on_top_bar_click(self, event):
        logging.info("Top bar clicked")
        self.top_bar_click_count += 1
        logging.info(f"Click count: {self.top_bar_click_count}")
        if self.top_bar_click_count == 3:
            logging.info("Toggling fullscreen")
            self.toggle_fullscreen()
            self.top_bar_click_count = 0
        else:
            self.after(500, self.reset_top_bar_click_count)

    def reset_top_bar_click_count(self):
        self.top_bar_click_count = 0

    def toggle_fullscreen(self):
        logging.info(f"Toggling fullscreen. Current state: {self.fullscreen}")
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            logging.info("Entering fullscreen mode")
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        else:
            logging.info("Exiting fullscreen mode")
            self.geometry(f"{self.winfo_width()}x{self.winfo_height()}+0+0")
        self.update_idletasks()
        logging.info(f"Fullscreen state after toggle: {self.fullscreen}")

    def exit_fullscreen(self, event=None):
        self.fullscreen = False
        self.attributes("-fullscreen", False)
        self.geometry(f"{self.winfo_width()}x{self.winfo_height()}+0+0")

if __name__ == "__main__":
    server_interface = ServerInterface()
    if len(sys.argv) > 1 and sys.argv[1] == "--fullscreen":
        server_interface.toggle_fullscreen()
    server_interface.mainloop()