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
import ctypes.wintypes

SERVER = "classguard-backend.onrender.com"
HTTP_SCHEME = "https" if "localhost" not in SERVER and "127.0.0.1" not in SERVER else "http"
WS_SCHEME = "wss" if "localhost" not in SERVER and "127.0.0.1" not in SERVER else "ws"

HTTP_URL = f"{HTTP_SCHEME}://{SERVER}"
AI_URL = "http://localhost:8001"
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
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        return buf.value
    except Exception:
        return ""


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ClassGuard - Setup")
        self.root.geometry("520x380")
        self.root.resizable(False, False)

        token = load_token()
        if token:
            self.root.after(100, lambda: self.try_reconnect(token))
        else:
            self.show_setup()

    def show_setup(self, error_msg=""):
        for w in self.root.winfo_children():
            w.destroy()

        frame = ttk.Frame(self.root, padding=40)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ClassGuard", font=("Segoe UI", 26, "bold")).pack(pady=(0, 5))
        ttk.Label(frame, text="Classroom Focus Monitor", font=("Segoe UI", 11), foreground="gray").pack(pady=(0, 25))

        ttk.Label(frame, text="Enter your unique code:", font=("Segoe UI", 11)).pack()

        self.code_var = tk.StringVar()
        code_entry = ttk.Entry(frame, textvariable=self.code_var, font=("Consolas", 20), justify="center")
        code_entry.pack(pady=10, ipady=6, fill="x")
        code_entry.focus()

        self.status_var = tk.StringVar(value=error_msg)
        status_color = "red" if error_msg else "gray"
        ttk.Label(frame, textvariable=self.status_var, font=("Segoe UI", 9), foreground=status_color).pack()

        ttk.Button(frame, text="Connect", command=self.connect).pack(pady=(15, 0), ipadx=25, ipady=4)

        self.root.bind("<Return>", lambda e: self.connect())

    def connect(self):
        code = self.code_var.get().strip().upper()
        if not code:
            self.status_var.set("Please enter a code")
            return

        self.status_var.set("Connecting...")
        self.root.update()

        try:
            resp = requests.post(f"{HTTP_URL}/api/students/link-device", json={"code": code}, timeout=10)
            data = resp.json()

            if data.get("success"):
                save_token(data["device_token"])
                self.root.destroy()
                AgentApp(data["device_token"], data["student_name"], data["section"]).run()
            else:
                self.show_setup(data.get("message", "Invalid code"))
        except requests.exceptions.ConnectionError:
            self.show_setup("Cannot reach server. Is the faculty's backend running on port 8000?")
        except Exception as e:
            self.show_setup(f"Error: {e}")

    def try_reconnect(self, token):
        for w in self.root.winfo_children():
            w.destroy()
        frame = ttk.Frame(self.root, padding=40)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="ClassGuard", font=("Segoe UI", 24, "bold")).pack(pady=(0, 10))
        ttk.Label(frame, text="Reconnecting...", font=("Segoe UI", 12)).pack()
        ttk.Label(frame, text="Please wait", font=("Segoe UI", 9), foreground="gray").pack(pady=(10, 0))
        self.root.update()

        try:
            resp = requests.post(f"{HTTP_URL}/api/monitoring/reconnect", json={"device_token": token}, timeout=10)
            data = resp.json()
            if data.get("ok"):
                self.root.destroy()
                AgentApp(token, data["student_name"], data["section"]).run()
                return
        except Exception:
            pass

        clear_token()
        self.show_setup("Session expired. Please re-enter your code.")


class AgentApp:
    def __init__(self, device_token, student_name, section):
        self.device_token = device_token
        self.student_name = student_name
        self.section = section
        self.running = True
        self.monitoring_active = False
        self.root = tk.Tk()
        self.root.title(f"ClassGuard - {student_name}")
        self.root.geometry("420x230")
        self.root.resizable(False, False)
        self.setup_ui()

    def setup_ui(self):
        frame = ttk.Frame(self.root, padding=25)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Connected", font=("Segoe UI", 10), foreground="green").pack()
        ttk.Label(frame, text=self.student_name, font=("Segoe UI", 18, "bold")).pack()
        ttk.Label(frame, text=f"Section {self.section}", font=("Segoe UI", 10), foreground="gray").pack(pady=(0, 12))

        self.status_var = tk.StringVar(value="Connected to server")
        ttk.Label(frame, textvariable=self.status_var, font=("Segoe UI", 9)).pack()

        self.window_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.window_var, font=("Segoe UI", 8), foreground="gray", wraplength=370).pack(pady=(5, 10))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Disconnect", command=self.disconnect).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Request Pause", command=self.request_pause).pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

    def update_status(self, text, color="black"):
        self.status_var.config(text=text, foreground=color)
        self.root.update()

    def run(self):
        threading.Thread(target=self.ws_thread, daemon=True).start()
        threading.Thread(target=self.heartbeat_thread, daemon=True).start()
        threading.Thread(target=self.capture_and_classify_thread, daemon=True).start()
        self.root.mainloop()

    def ws_thread(self):
        url = f"{WS_SCHEME}://{SERVER}/ws/agent?device_token={self.device_token}"
        while self.running:
            try:
                self.ws = websocket.WebSocket()
                self.ws.connect(url, timeout=5)
                self.update_status("Connected to server", "green")
                self.ws.settimeout(5)

                while self.running:
                    try:
                        msg = json.loads(self.ws.recv())
                        event = msg.get("event")
                        data = msg.get("data", {})

                        if event == "monitoring_started":
                            self.monitoring_active = True
                            self.update_status("Monitoring active", "green")
                        elif event == "monitoring_stopped":
                            self.monitoring_active = False
                            self.update_status("Monitoring inactive", "gray")
                        elif event == "monitoring_paused":
                            self.monitoring_active = False
                            reason = data.get("reason", "")
                            self.update_status(f"Paused: {reason}", "orange")
                        elif event == "warning":
                            level = data.get("level", 1)
                            message = data.get("message", "")
                            self.update_status(f"Warning ({level}): {message}", "red")
                    except websocket.WebSocketTimeoutException:
                        continue
                    except Exception:
                        break
            except Exception:
                self.update_status("Disconnected. Reconnecting...", "red")
                time.sleep(3)

    def heartbeat_thread(self):
        while self.running:
            try:
                requests.post(f"{HTTP_URL}/api/monitoring/heartbeat",
                             json={"device_token": self.device_token}, timeout=5)
            except Exception:
                pass
            time.sleep(10)

    def capture_and_classify_thread(self):
        time.sleep(2)
        import base64
        import io
        from PIL import ImageGrab
        
        while self.running:
            try:
                if self.monitoring_active:
                    title = get_active_window_title()
                    self.window_var.set(f"Active: {title[:60]}")
                    
                    # Capture screen
                    img = ImageGrab.grab()
                    img.thumbnail((960, 540)) # Resize to fit network payload nicely
                    
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", quality=55)
                    img_bytes = buffer.getvalue()
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    if hasattr(self, "ws") and self.ws:
                        payload = {
                            "event": "screen_frame",
                            "screenshot": img_b64,
                            "window_title": title
                        }
                        try:
                            self.ws.send(json.dumps(payload))
                        except Exception:
                            pass
            except Exception as e:
                print("Screen capture thread error:", e)
            time.sleep(1)

    def request_pause(self):
        def submit():
            reason = reason_var.get().strip()
            if not reason:
                return
            try:
                requests.post(f"{HTTP_URL}/api/disable-requests/",
                             json={"device_id": self.device_token, "reason": reason}, timeout=10)
                messagebox.showinfo("Request Sent", "Your request has been sent to the faculty.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send request: {e}")
            pw.destroy()

        pw = tk.Toplevel(self.root)
        pw.title("Request Pause")
        pw.geometry("350x200")
        pw.resizable(False, False)
        ttk.Label(pw, text="Reason for pausing:", font=("Segoe UI", 11)).pack(pady=(15, 5))
        reason_var = tk.StringVar()
        entry = ttk.Entry(pw, textvariable=reason_var, font=("Segoe UI", 10))
        entry.pack(pady=5, padx=20, fill="x")
        entry.focus()
        ttk.Button(pw, text="Submit Request", command=submit).pack(pady=15)
        pw.bind("<Return>", lambda e: submit())

    def disconnect(self):
        self.running = False
        try:
            self.ws.close()
        except Exception:
            pass
        clear_token()
        self.root.destroy()


if __name__ == "__main__":
    SetupWindow()
