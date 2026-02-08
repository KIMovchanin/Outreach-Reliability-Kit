from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT_DIR = Path(__file__).resolve().parents[1]
POT_DIR = ROOT_DIR / "pot"
CHECK_SCRIPT = POT_DIR / "scripts" / "check_emails.py"
TG_SCRIPT = POT_DIR / "scripts" / "send_telegram.py"
POT_ENV_FILE = POT_DIR / ".env"


class ProcessRunner:
    def __init__(self, output_cb) -> None:
        self._output_cb = output_cb
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[str] | None = None
        self._queue: queue.Queue[str] = queue.Queue()

    def run(self, cmd: list[str], cwd: Path) -> None:
        if self.is_running():
            raise RuntimeError("A process is already running")

        def worker() -> None:
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert self._proc.stdout is not None
                for line in self._proc.stdout:
                    self._queue.put(line)
                code = self._proc.wait()
                self._queue.put(f"\n[exit code: {code}]\n")
            except Exception as exc:  # noqa: BLE001
                self._queue.put(f"\n[process error: {exc}]\n")
            finally:
                self._proc = None

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def poll_output(self) -> None:
        while True:
            try:
                chunk = self._queue.get_nowait()
            except queue.Empty:
                break
            self._output_cb(chunk)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("POT GUI")
        self.geometry("1240x820")

        self.style = ttk.Style(self)
        self.theme_var = tk.StringVar(value="Light")

        self.runner = ProcessRunner(self._append_output)
        self._build_ui()
        self._apply_theme("Light")
        self._schedule_poll()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.email_tab = ttk.Frame(self.notebook)
        self.tg_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.email_tab, text="Email Check")
        self.notebook.add(self.tg_tab, text="Telegram")
        self.notebook.add(self.settings_tab, text="Settings")

        self._build_email_tab()
        self._build_telegram_tab()
        self._build_settings_tab()

        output_frame = ttk.LabelFrame(self, text="Output")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.output = tk.Text(output_frame, height=15, wrap=tk.WORD)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(buttons, text="Stop Current Process", command=self._stop_process).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Clear Output", command=lambda: self.output.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=8)

    def _build_email_tab(self) -> None:
        frame = self.email_tab
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        self.email_file_var = tk.StringVar(value=str(POT_DIR / "data" / "emails.txt"))
        self.email_list_var = tk.StringVar()
        self.format_var = tk.StringVar(value="table")
        self.timeout_var = tk.StringVar(value="8")
        self.max_mx_var = tk.StringVar(value="2")
        self.domain_pause_var = tk.StringVar(value="0.3")
        self.mail_from_var = tk.StringVar(value="verify@yourdomain.test")
        self.helo_var = tk.StringVar(value="localhost")
        self.dns_server_var = tk.StringVar(value="1.1.1.1,8.8.8.8")
        self.dns_retries_var = tk.StringVar(value="3")
        self.smtp_retries_var = tk.StringVar(value="1")
        self.smtp_cooldown_var = tk.StringVar(value="300")
        self.log_level_var = tk.StringVar(value="INFO")
        self.log_file_var = tk.StringVar(value="log.txt")

        self.skip_smtp_var = tk.BooleanVar(value=False)
        self.self_check_var = tk.BooleanVar(value=False)

        ttk.Label(frame, text="Emails file").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.email_file_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        ttk.Button(frame, text="Browse", command=self._pick_email_file).grid(row=0, column=3, sticky="e", padx=8, pady=6)

        ttk.Label(frame, text="Emails (space separated)").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.email_list_var).grid(row=1, column=1, columnspan=3, sticky="ew", padx=8, pady=6)

        self._add_labeled_entry(frame, "Format", self.format_var, 2, col=0, combobox_values=["table", "jsonl"])
        self._add_labeled_entry(frame, "Timeout", self.timeout_var, 2, col=2)
        self._add_labeled_entry(frame, "Max MX tries", self.max_mx_var, 3, col=0)
        self._add_labeled_entry(frame, "Domain pause", self.domain_pause_var, 3, col=2)
        self._add_labeled_entry(frame, "MAIL FROM", self.mail_from_var, 4, col=0)
        self._add_labeled_entry(frame, "HELO host", self.helo_var, 4, col=2)
        self._add_labeled_entry(frame, "DNS servers (comma)", self.dns_server_var, 5, col=0)
        self._add_labeled_entry(frame, "DNS retries", self.dns_retries_var, 5, col=2)
        self._add_labeled_entry(frame, "SMTP retries", self.smtp_retries_var, 6, col=0)
        self._add_labeled_entry(frame, "SMTP cooldown", self.smtp_cooldown_var, 6, col=2)
        self._add_labeled_entry(frame, "Log level", self.log_level_var, 7, col=0, combobox_values=["DEBUG", "INFO", "WARNING", "ERROR"])
        self._add_labeled_entry(frame, "Log file", self.log_file_var, 7, col=2)

        ttk.Checkbutton(frame, text="Skip SMTP (--skip-smtp)", variable=self.skip_smtp_var).grid(
            row=8, column=0, sticky="w", padx=8, pady=6
        )
        ttk.Checkbutton(frame, text="Self-check only (--self-check)", variable=self.self_check_var).grid(
            row=8, column=2, sticky="w", padx=8, pady=6
        )

        ttk.Button(frame, text="Run Email Check", command=self._run_email_check).grid(row=9, column=0, columnspan=4, pady=10)

    def _build_telegram_tab(self) -> None:
        frame = self.tg_tab
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(6, weight=1)

        self.tg_file_var = tk.StringVar(value=str(POT_DIR / "data" / "message.txt"))
        self.tg_token_var = tk.StringVar(value=os.getenv("BOT_TOKEN", ""))
        self.tg_chat_var = tk.StringVar(value=os.getenv("CHAT_ID", ""))
        self.tg_log_level_var = tk.StringVar(value="INFO")

        ttk.Label(frame, text="Message file").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(frame, textvariable=self.tg_file_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        ttk.Button(frame, text="Browse", command=self._pick_message_file).grid(row=0, column=3, sticky="e", padx=8, pady=6)

        ttk.Label(frame, text="BOT_TOKEN").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        token_entry = ttk.Entry(frame, textvariable=self.tg_token_var)
        token_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        self._bind_clipboard_shortcuts(token_entry)
        ttk.Button(frame, text="Paste", command=lambda: self._paste_into_var(self.tg_token_var)).grid(
            row=1, column=3, sticky="e", padx=8, pady=6
        )

        ttk.Label(frame, text="CHAT_ID").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        chat_entry = ttk.Entry(frame, textvariable=self.tg_chat_var)
        chat_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        self._bind_clipboard_shortcuts(chat_entry)
        ttk.Button(frame, text="Paste", command=lambda: self._paste_into_var(self.tg_chat_var)).grid(
            row=2, column=3, sticky="e", padx=8, pady=6
        )

        ttk.Label(frame, text="Log level").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ttk.Combobox(frame, textvariable=self.tg_log_level_var, values=["DEBUG", "INFO", "WARNING", "ERROR"], state="readonly").grid(
            row=3, column=1, sticky="ew", padx=8, pady=6
        )

        actions = ttk.Frame(frame)
        actions.grid(row=4, column=0, columnspan=4, sticky="w", padx=8, pady=8)

        ttk.Button(actions, text="Send Telegram Message", command=self._run_telegram_send).pack(side=tk.LEFT)
        ttk.Button(actions, text="Save Token/Chat to pot/.env", command=self._save_telegram_env).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Load Message from File", command=self._load_telegram_message_file).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Save Message to File", command=self._save_telegram_message_file).pack(side=tk.LEFT, padx=8)

        ttk.Label(
            frame,
            text="Edit message below. On send, GUI saves editor content to the selected file first.",
        ).grid(row=5, column=0, columnspan=4, sticky="w", padx=8, pady=6)

        editor_frame = ttk.LabelFrame(frame, text="Message Editor")
        editor_frame.grid(row=6, column=0, columnspan=4, sticky="nsew", padx=8, pady=8)
        editor_frame.rowconfigure(0, weight=1)
        editor_frame.columnconfigure(0, weight=1)

        self.tg_message_text = tk.Text(editor_frame, height=14, wrap=tk.WORD)
        self.tg_message_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self._bind_clipboard_shortcuts(self.tg_message_text)

        editor_scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=self.tg_message_text.yview)
        editor_scroll.grid(row=0, column=1, sticky="ns", pady=6)
        self.tg_message_text.configure(yscrollcommand=editor_scroll.set)

        self._load_telegram_message_file(show_warning=False)

    def _build_settings_tab(self) -> None:
        frame = self.settings_tab
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Theme").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        ttk.Combobox(frame, textvariable=self.theme_var, values=["Light", "Dark"], state="readonly").grid(
            row=0, column=1, sticky="w", padx=10, pady=10
        )
        ttk.Button(frame, text="Apply Theme", command=lambda: self._apply_theme(self.theme_var.get())).grid(
            row=0, column=2, sticky="w", padx=10, pady=10
        )

        ttk.Label(frame, text="Theme applies to tabs, forms, output and Telegram message editor.").grid(
            row=1, column=0, columnspan=3, sticky="w", padx=10, pady=6
        )

    def _apply_theme(self, theme_name: str) -> None:
        base_theme = "clam"
        if base_theme in self.style.theme_names():
            self.style.theme_use(base_theme)

        is_dark = theme_name.lower() == "dark"
        if is_dark:
            bg = "#1e1e1e"
            fg = "#f0f0f0"
            field_bg = "#2b2b2b"
            select_bg = "#3b82f6"
        else:
            bg = "#f4f4f4"
            fg = "#111111"
            field_bg = "#ffffff"
            select_bg = "#2563eb"

        self.configure(bg=bg)
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg)
        self.style.configure("TCheckbutton", background=bg, foreground=fg)
        self.style.configure("TButton", background=bg, foreground=fg)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=fg)
        self.style.configure("TNotebook", background=bg)
        self.style.configure("TNotebook.Tab", background=bg, foreground=fg)
        self.style.map("TNotebook.Tab", background=[("selected", field_bg)], foreground=[("selected", fg)])
        self.style.configure("TEntry", fieldbackground=field_bg, foreground=fg)
        self.style.configure("TCombobox", fieldbackground=field_bg, foreground=fg)

        text_widgets = [getattr(self, "output", None), getattr(self, "tg_message_text", None)]
        for widget in text_widgets:
            if isinstance(widget, tk.Text):
                widget.configure(bg=field_bg, fg=fg, insertbackground=fg, selectbackground=select_bg)

    def _add_labeled_entry(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        row: int,
        col: int,
        combobox_values: list[str] | None = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=8, pady=6)
        if combobox_values:
            widget = ttk.Combobox(parent, textvariable=var, values=combobox_values, state="readonly")
        else:
            widget = ttk.Entry(parent, textvariable=var)
        widget.grid(row=row, column=col + 1, sticky="ew", padx=8, pady=6)

    def _pick_email_file(self) -> None:
        path = filedialog.askopenfilename(title="Select emails file", filetypes=[("Text files", "*.txt"), ("All files", "*")])
        if path:
            self.email_file_var.set(path)

    def _pick_message_file(self) -> None:
        path = filedialog.askopenfilename(title="Select message file", filetypes=[("Text files", "*.txt"), ("All files", "*")])
        if path:
            self.tg_file_var.set(path)
            self._load_telegram_message_file(show_warning=False)

    def _bind_clipboard_shortcuts(self, widget: tk.Widget) -> None:
        widget.bind("<Control-v>", self._on_paste)
        widget.bind("<Control-V>", self._on_paste)
        widget.bind("<Shift-Insert>", self._on_paste)

    def _on_paste(self, event: tk.Event) -> str:
        widget = event.widget
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return "break"

        if isinstance(widget, tk.Text):
            widget.insert(tk.INSERT, text)
        else:
            try:
                widget.insert(tk.INSERT, text)
            except tk.TclError:
                pass
        return "break"

    def _paste_into_var(self, var: tk.StringVar) -> None:
        try:
            value = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("Clipboard", "Clipboard is empty or unavailable")
            return
        var.set(value)

    def _load_telegram_message_file(self, show_warning: bool = True) -> None:
        file_path = Path(self.tg_file_var.get().strip())
        if not file_path.exists():
            if show_warning:
                messagebox.showwarning("File not found", f"Message file does not exist: {file_path}")
            self.tg_message_text.delete("1.0", tk.END)
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Read error", f"Cannot read message file: {exc}")
            return

        self.tg_message_text.delete("1.0", tk.END)
        self.tg_message_text.insert("1.0", content)

    def _save_telegram_message_file(self, show_message: bool = True) -> bool:
        file_path = Path(self.tg_file_var.get().strip())
        if not str(file_path):
            messagebox.showerror("Input error", "Message file path is empty")
            return False

        content = self.tg_message_text.get("1.0", tk.END)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Save error", f"Cannot save message file: {exc}")
            return False

        if show_message:
            messagebox.showinfo("Saved", f"Saved message to {file_path}")
        return True

    def _run_email_check(self) -> None:
        cmd = [sys.executable, str(CHECK_SCRIPT)]

        if self.self_check_var.get():
            cmd.append("--self-check")
        else:
            email_file = self.email_file_var.get().strip()
            email_list = self.email_list_var.get().strip()
            if email_file:
                cmd.extend(["--file", email_file])
            if email_list:
                cmd.extend(["--emails", *email_list.split()])
            if not email_file and not email_list:
                messagebox.showerror("Input error", "Provide emails file or emails list")
                return

            cmd.extend(["--format", self.format_var.get().strip() or "table"])
            cmd.extend(["--timeout", self.timeout_var.get().strip() or "8"])
            cmd.extend(["--max-mx-tries", self.max_mx_var.get().strip() or "2"])
            cmd.extend(["--domain-pause", self.domain_pause_var.get().strip() or "0.3"])
            cmd.extend(["--mail-from", self.mail_from_var.get().strip() or "verify@yourdomain.test"])
            cmd.extend(["--helo-host", self.helo_var.get().strip() or "localhost"])
            cmd.extend(["--dns-retries", self.dns_retries_var.get().strip() or "3"])
            cmd.extend(["--smtp-retries", self.smtp_retries_var.get().strip() or "1"])
            cmd.extend(["--smtp-host-cooldown", self.smtp_cooldown_var.get().strip() or "300"])

            dns_servers = [item.strip() for item in self.dns_server_var.get().split(",") if item.strip()]
            for server in dns_servers:
                cmd.extend(["--dns-server", server])

            if self.skip_smtp_var.get():
                cmd.append("--skip-smtp")

            cmd.extend(["--log-level", self.log_level_var.get().strip() or "INFO"])
            cmd.extend(["--log-file", self.log_file_var.get().strip() or "log.txt"])

        self._start_process(cmd)

    def _run_telegram_send(self) -> None:
        msg_file = self.tg_file_var.get().strip()
        if not msg_file:
            messagebox.showerror("Input error", "Message file is required")
            return

        if not self._save_telegram_message_file(show_message=False):
            return

        cmd = [
            sys.executable,
            str(TG_SCRIPT),
            "--file",
            msg_file,
            "--log-level",
            self.tg_log_level_var.get().strip() or "INFO",
        ]

        token = self.tg_token_var.get().strip()
        chat_id = self.tg_chat_var.get().strip()
        if token:
            cmd.extend(["--token", token])
        if chat_id:
            cmd.extend(["--chat-id", chat_id])

        self._start_process(cmd)

    def _save_telegram_env(self) -> None:
        token = self.tg_token_var.get().strip()
        chat_id = self.tg_chat_var.get().strip()
        if not token or not chat_id:
            messagebox.showerror("Input error", "BOT_TOKEN and CHAT_ID are required to save .env")
            return

        POT_ENV_FILE.write_text(f"BOT_TOKEN={token}\nCHAT_ID={chat_id}\n", encoding="utf-8")
        messagebox.showinfo("Saved", f"Saved credentials to {POT_ENV_FILE}")

    def _start_process(self, cmd: list[str]) -> None:
        self._append_output(f"\n$ {' '.join(cmd)}\n")
        try:
            self.runner.run(cmd, cwd=ROOT_DIR)
        except RuntimeError as exc:
            messagebox.showwarning("Process running", str(exc))

    def _stop_process(self) -> None:
        self.runner.stop()
        self._append_output("\n[process terminated]\n")

    def _append_output(self, text: str) -> None:
        self.output.insert(tk.END, text)
        self.output.see(tk.END)

    def _schedule_poll(self) -> None:
        self.runner.poll_output()
        self.after(150, self._schedule_poll)


def main() -> None:
    if not CHECK_SCRIPT.exists() or not TG_SCRIPT.exists():
        raise SystemExit("Expected scripts not found. Run GUI from project repository.")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
