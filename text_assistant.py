import threading
import time
import sys
import os
import json
import tkinter as tk
from tkinter import ttk, scrolledtext
import pyperclip
import keyboard
import requests
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_BACKEND_URL = "http://localhost:8080"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"backend_url": DEFAULT_BACKEND_URL}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ─── BACKEND API ──────────────────────────────────────────────────────────────
ACTIONS = {
    "🌐 Перевести на русский":    "TRANSLATE_RU",
    "🌐 Перевести на английский": "TRANSLATE_EN",
    "✏️ Исправить орфографию":    "SPELLING",
    "📝 Расставить запятые":      "PUNCTUATION",
    "🔄 Перефразировать":         "REPHRASE",
    "💡 Объяснить слово/фразу":   "EXPLAIN",
}

def call_backend(action_name: str, text: str) -> str:
    backend_url = load_config().get("backend_url", DEFAULT_BACKEND_URL).rstrip("/")
    if not backend_url:
        return "⚠️ URL сервера не задан. Откройте настройки (иконка в трее → Настройки)."
    try:
        response = requests.post(
            f"{backend_url}/api/process",
            json={"action": ACTIONS[action_name], "text": text},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["result"]
    except requests.exceptions.ConnectionError:
        return "❌ Не удалось подключиться к серверу. Проверьте URL в настройках."
    except requests.exceptions.Timeout:
        return "❌ Сервер не ответил вовремя. Попробуйте ещё раз."
    except requests.exceptions.HTTPError as e:
        return f"❌ Ошибка сервера: {e.response.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {e}"

# ─── POPUP WINDOW ─────────────────────────────────────────────────────────────
class PopupMenu:
    def __init__(self):
        self.root = None
        self.result_win = None

    def show_menu(self, selected_text: str):
        if self.root and self.root.winfo_exists():
            self.root.destroy()

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e2e")

        try:
            import win32api
            x, y = win32api.GetCursorPos()
        except Exception:
            x, y = 100, 100
        self.root.geometry(f"+{x+10}+{y+10}")

        frame = tk.Frame(self.root, bg="#1e1e2e", padx=2, pady=2)
        frame.pack()

        tk.Label(frame, text="✦ Текстовый помощник",
                 bg="#313244", fg="#cdd6f4",
                 font=("Segoe UI", 9, "bold"),
                 padx=10, pady=5).pack(fill="x")

        preview = selected_text[:60] + ("…" if len(selected_text) > 60 else "")
        tk.Label(frame, text=f'"{preview}"',
                 bg="#1e1e2e", fg="#6c7086",
                 font=("Segoe UI", 8), wraplength=240,
                 padx=8, pady=3).pack(fill="x")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=2)

        for action_name in ACTIONS:
            btn = tk.Button(
                frame, text=action_name,
                bg="#1e1e2e", fg="#cdd6f4",
                activebackground="#313244", activeforeground="#89b4fa",
                font=("Segoe UI", 9),
                relief="flat", anchor="w",
                padx=12, pady=4, cursor="hand2",
                command=lambda a=action_name, t=selected_text: self._run_action(a, t)
            )
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#313244"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#1e1e2e"))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=2)

        tk.Button(frame, text="✕ Закрыть",
                  bg="#1e1e2e", fg="#6c7086",
                  activebackground="#313244",
                  font=("Segoe UI", 8),
                  relief="flat", padx=12, pady=3,
                  cursor="hand2",
                  command=self.root.destroy).pack(fill="x")

        self.root.bind("<FocusOut>", lambda e: self._close_if_unfocused())
        self.root.focus_force()
        self.root.mainloop()

    def _close_if_unfocused(self):
        try:
            if self.root and self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass

    def _run_action(self, action_name: str, text: str):
        try:
            if self.root and self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass
        threading.Thread(target=self._show_result, args=(action_name, text), daemon=True).start()

    def _show_result(self, action_name: str, text: str):
        result = call_backend(action_name, text)
        self._open_result_window(action_name, text, result)

    def _open_result_window(self, action_name, original, result):
        win = tk.Tk()
        win.title(action_name)
        win.configure(bg="#1e1e2e")
        win.attributes("-topmost", True)
        win.geometry("480x360")
        win.resizable(True, True)

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"480x360+{(sw-480)//2}+{(sh-360)//2}")

        tk.Label(win, text=action_name, bg="#313244", fg="#89b4fa",
                 font=("Segoe UI", 11, "bold"), padx=10, pady=8).pack(fill="x")

        tk.Label(win, text="Результат:", bg="#1e1e2e", fg="#a6adc8",
                 font=("Segoe UI", 9), anchor="w", padx=10).pack(fill="x")

        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Segoe UI", 10),
                                        bg="#313244", fg="#cdd6f4",
                                        insertbackground="#cdd6f4",
                                        relief="flat", padx=8, pady=8)
        txt.pack(fill="both", expand=True, padx=10, pady=4)
        txt.insert("1.0", result)

        btn_frame = tk.Frame(win, bg="#1e1e2e")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def copy_result():
            pyperclip.copy(txt.get("1.0", tk.END).strip())
            copy_btn.config(text="✓ Скопировано!")
            win.after(1500, lambda: copy_btn.config(text="📋 Копировать"))

        copy_btn = tk.Button(btn_frame, text="📋 Копировать",
                             bg="#89b4fa", fg="#1e1e2e",
                             font=("Segoe UI", 9, "bold"),
                             relief="flat", padx=12, pady=5,
                             cursor="hand2", command=copy_result)
        copy_btn.pack(side="left", padx=(0, 6))

        tk.Button(btn_frame, text="✕ Закрыть",
                  bg="#313244", fg="#cdd6f4",
                  font=("Segoe UI", 9),
                  relief="flat", padx=12, pady=5,
                  cursor="hand2", command=win.destroy).pack(side="left")

        win.mainloop()

popup = PopupMenu()

# ─── HOTKEY LISTENER ──────────────────────────────────────────────────────────
def on_hotkey():
    try:
        original_clip = pyperclip.paste()
    except Exception:
        original_clip = ""

    keyboard.send("ctrl+c")
    time.sleep(0.15)

    try:
        selected = pyperclip.paste()
    except Exception:
        selected = ""

    if not selected or selected == original_clip:
        return

    if selected.strip():
        threading.Thread(target=popup.show_menu, args=(selected,), daemon=True).start()

# ─── SETTINGS WINDOW ──────────────────────────────────────────────────────────
def open_settings():
    win = tk.Tk()
    win.title("Настройки — Текстовый помощник")
    win.configure(bg="#1e1e2e")
    win.geometry("440x220")
    win.resizable(False, False)
    win.attributes("-topmost", True)

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"440x220+{(sw-440)//2}+{(sh-220)//2}")

    tk.Label(win, text="⚙️ Настройки", bg="#313244", fg="#89b4fa",
             font=("Segoe UI", 12, "bold"), padx=10, pady=10).pack(fill="x")

    tk.Label(win, text="URL сервера:", bg="#1e1e2e", fg="#a6adc8",
             font=("Segoe UI", 9), anchor="w", padx=14).pack(fill="x", pady=(10, 2))

    entry = tk.Entry(win, font=("Segoe UI", 9), bg="#313244", fg="#cdd6f4",
                     insertbackground="#cdd6f4", relief="flat", width=50)
    entry.pack(fill="x", padx=14)
    entry.insert(0, load_config().get("backend_url", DEFAULT_BACKEND_URL))

    tk.Label(win, text="Горячая клавиша: Ctrl + Shift + A (выделите текст сначала)",
             bg="#1e1e2e", fg="#6c7086", font=("Segoe UI", 8),
             anchor="w", padx=14).pack(fill="x", pady=(6, 0))

    def save():
        cfg = load_config()
        cfg["backend_url"] = entry.get().strip()
        save_config(cfg)
        win.destroy()

    btn_f = tk.Frame(win, bg="#1e1e2e")
    btn_f.pack(pady=14)
    tk.Button(btn_f, text="💾 Сохранить", bg="#89b4fa", fg="#1e1e2e",
              font=("Segoe UI", 9, "bold"), relief="flat",
              padx=14, pady=6, cursor="hand2", command=save).pack(side="left", padx=6)
    tk.Button(btn_f, text="Отмена", bg="#313244", fg="#cdd6f4",
              font=("Segoe UI", 9), relief="flat",
              padx=14, pady=6, cursor="hand2", command=win.destroy).pack(side="left")

    win.mainloop()

# ─── TRAY ICON ────────────────────────────────────────────────────────────────
def create_tray_image():
    img = Image.new("RGB", (64, 64), color="#1e1e2e")
    d = ImageDraw.Draw(img)
    d.ellipse([8, 8, 56, 56], fill="#89b4fa")
    d.text((22, 18), "T", fill="#1e1e2e")
    return img

def run_tray():
    menu = Menu(
        MenuItem("⚙️ Настройки", lambda icon, item: threading.Thread(target=open_settings, daemon=True).start()),
        MenuItem("❌ Выход", lambda icon, item: (icon.stop(), os._exit(0)))
    )
    icon = Icon("TextAssistant", create_tray_image(),
                "Текстовый помощник\nCtrl+Shift+A", menu)
    icon.run()

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    keyboard.add_hotkey("ctrl+shift+a", on_hotkey)

    if not load_config().get("backend_url"):
        threading.Thread(target=open_settings, daemon=True).start()

    print("✅ Текстовый помощник запущен.")
    print("   Выделите текст в любом приложении → нажмите Ctrl+Shift+A")
    print("   Иконка в трее → Настройки (укажите URL сервера)")

    run_tray()