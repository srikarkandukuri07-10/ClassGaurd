import os
import sys
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import requests
import websocket
import ctypes
from datetime import datetime, timezone

SERVER = "classguard-backend.onrender.com"
HTTP_URL = f"https://{SERVER}"
AI_URL = "https://classguard-ai.onrender.com"
TOKEN_FILE = "classguard_token.json"


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
            return data.get("device_token")
    return None


def save_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"device_token": token}, f)


def clear_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def get_active_window_title():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        len = ctypes.windll.user32.GetWindowTextW(hwnd, buf.as_mut_ptr(), length)
        if len > 0:
            return buf.value
        else:
            return ""
    except Exception:
        return ""


class AgentApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ClassGuard Student Agent")
        self.root.geometry("400x350")
        
        self.token = None
        self.ws = None
        self.running = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # Login Frame
        self.login_frame = tk.Frame(self.root, padx=20, pady=20)
        self.login_frame.pack(fill="both", expand=True)
        
        tk.Label(self.login_frame, text="Enter ClassGuard Code", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        self.code_entry = tk.Entry(self.login_frame, width=30, font=("Arial", 12))
        self.code_entry.pack(pady=(0, 10))
        
        tk.Label(self.login_frame, text="Server URL", font=("Arial", 10)).pack(pady=(0, 5))
        self.server_entry = tk.Entry(self.login_frame, width=30, font=("Arial", 10))
        self.server_entry.insert(0, HTTP_URL)
        self.server_entry.pack(pady=(0, 10))
        
        tk.Button(self.login_frame, text="Connect", command=self.connect, font=("Arial", 12, "bold")).pack(pady=(0, 5))
        
        # Dashboard Frame
        self.dashboard_frame = tk.Frame(self.root, padx=20, pady=20)
        self.dashboard_frame.pack(fill="both", expand=True)
        
        tk.Label(self.dashboard_frame, text="ClassGuard Dashboard", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        
        self.status_frame = tk.Frame(self.dashboard_frame)
        self.status_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.status_label = tk.Label(self.status_frame, text="Status: Disconnected", font=("Arial", 12))
        self.status_label.pack(pady=(5, 5))
        
        self.current_activity = tk.Label(self.status_frame, text="Activity: Not monitoring", font=("Arial", 10))
        self.current_activity.pack(pady=(5, 5))
        
        self.warning_label = tk.Label(self.status_frame, text="Warnings: 0", font=("Arial", 10, "bold"))
        self.warning_label.pack(pady=(5, 5))
        
        self.disconnect_button = tk.Button(self.dashboard_frame, text="Disconnect", command=self.disconnect, font=("Arial", 12))
        self.disconnect_button.pack(pady=(0, 10))
        
        self.dashboard_frame.pack_forget()
    
    def connect(self):
        code = self.code_entry.get().strip()
        server_url = self.server_entry.get().strip()
        
        if not code or not server_url:
            messagebox.showerror("Error", "Please enter both code and server URL")
            return
        
        try:
            # Register device and get token
            response = requests.post(
                f"{server_url}/api/devices/register",
                json={"student_code": code},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("device_token")
                if not token:
                    messagebox.showerror("Error", "No device token received")
                    return
                
                self.token = token
                save_token(token)
                self.connect_websocket(token, server_url)
            else:
                error_msg = response.json().get("detail", "Failed to connect")
                messagebox.showerror("Error", error_msg)
                
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {str(e)}")
    
    def connect_websocket(self, token, server_url):
        ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws = websocket.WebSocketApp(
            f"{ws_url}/ws/agent?device_token={token}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        def run_ws():
            self.ws.run_forever()
        
        threading.Thread(target=run_ws, daemon=True).start()
    
    def on_open(self, ws):
        print("WebSocket connection opened")
        self.running = True
        self.status_label.config(text="Status: Connected", fg="green")
        
        # Send heartbeat periodically
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        
        # Start monitoring window title
        threading.Thread(target=self.monitor_window, daemon=True).start()
    
    def heartbeat_loop(self):
        while self.running:
            try:
                requests.post(
                    f"{HTTP_URL}/api/monitoring/heartbeat",
                    json={"device_token": self.token},
                    timeout=10
                )
            except Exception:
                pass
            time.sleep(15)
    
    def monitor_window(self):
        while self.running:
            try:
                window_title = get_active_window_title()
                if window_title:
                    self.send_activity(window_title)
            except Exception:
                pass
            time.sleep(2)
    
    def send_activity(self, window_title):
        try:
            response = requests.post(
                f"{HTTP_URL}/api/ai/classify",
                json={
                    "device_id": self.token,
                    "window_title": window_title,
                    "image": None
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.current_activity.config(text=f"Activity: {result['status']}", fg="red" if result['status'] == "off-task" else "green")
                
                if result['status'] == "off-task":
                    self.warning_label.config(text=f"Warning: {self.warning_label.cget('text').split(':')[1].strip()}")
        except Exception:
            pass
    
    def on_message(self, ws, message):
        data = json.loads(message)
        event = data.get("event")
        
        if event == "warning":
            msg = data.get("data", {})
            level = msg.get("level", 0)
            message_text = msg.get("message", "Warning")
            reason = msg.get("reason", "")
            
            messagebox.showwarning("Warning", f"{message_text}\n\nReason: {reason}")
            
            current_warnings = self.warning_label.cget("text").split(":")[1].strip()
            self.warning_label.config(text=f"Warnings: {int(current_warnings) + 1}")
        
        elif event == "monitoring_stopped":
            self.running = False
            self.status_label.config(text="Status: Monitoring Stopped", fg="red")
            self.disconnect_button.config(state="normal")
        
        elif event == "monitoring_started":
            self.status_label.config(text="Status: Monitoring Active", fg="green")
    
    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")
        self.running = False
        self.status_label.config(text="Status: Error", fg="red")
    
    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket connection closed")
        self.running = False
        self.status_label.config(text="Status: Disconnected", fg="red")
        self.disconnect_button.config(state="normal")
    
    def disconnect(self):
        if self.ws:
            self.ws.close()
        self.running = False
        self.token = None
        clear_token()
        self.status_label.config(text="Status: Disconnected", fg="black")
        self.current_activity.config(text="Activity: Not monitoring")
        self.warning_label.config(text="Warnings: 0")
        self.dashboard_frame.pack_forget()
        self.login_frame.pack(fill="both", expand=True)


def main():
    root = tk.Tk()
    app = AgentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
