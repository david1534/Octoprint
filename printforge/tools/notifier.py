"""
Windows notification + profile picker popup for the auto-slicer.

Shows a tkinter dialog when a new STL is detected, letting the user
choose a slicing profile. Also shows toast notifications for results.
"""

import threading
import tkinter as tk
from tkinter import ttk

from profile_loader import PROFILE_LABELS


def pick_profile(
    filename: str,
    default: str = "functional",
    timeout_seconds: int = 60,
) -> str | None:
    """
    Show a popup dialog for the user to pick a slicing profile.

    Args:
        filename: Name of the detected STL file.
        default: Default profile to pre-select.
        timeout_seconds: Auto-close after this many seconds (uses default).

    Returns:
        Profile name string, or None if cancelled.
    """
    result = {"profile": None, "confirmed": False}

    def on_ok():
        result["profile"] = selected.get()
        result["confirmed"] = True
        root.destroy()

    def on_cancel():
        root.destroy()

    def on_timeout():
        if root.winfo_exists():
            # Auto-select default on timeout
            result["profile"] = default
            result["confirmed"] = True
            root.destroy()

    root = tk.Tk()
    root.title("PrintForge Auto-Slicer")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # Center on screen
    root.update_idletasks()
    w, h = 420, 320
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # Dark theme colors
    bg = "#1e1e2e"
    fg = "#cdd6f4"
    accent = "#89b4fa"
    btn_bg = "#313244"
    btn_hover = "#45475a"
    root.configure(bg=bg)

    # Header
    header = tk.Label(
        root, text="New STL Detected", font=("Segoe UI", 14, "bold"),
        bg=bg, fg=fg,
    )
    header.pack(pady=(16, 4))

    filename_label = tk.Label(
        root, text=filename, font=("Segoe UI", 10),
        bg=bg, fg=accent, wraplength=380,
    )
    filename_label.pack(pady=(0, 12))

    tk.Label(
        root, text="Select slicing profile:", font=("Segoe UI", 10),
        bg=bg, fg=fg, anchor="w",
    ).pack(padx=20, anchor="w")

    # Profile radio buttons
    selected = tk.StringVar(value=default)
    profiles_frame = tk.Frame(root, bg=bg)
    profiles_frame.pack(padx=20, pady=(4, 12), fill="x")

    for name, label in PROFILE_LABELS.items():
        rb = tk.Radiobutton(
            profiles_frame, text=label, variable=selected, value=name,
            font=("Segoe UI", 9), bg=bg, fg=fg, selectcolor="#313244",
            activebackground=bg, activeforeground=accent,
            highlightthickness=0, anchor="w",
        )
        rb.pack(fill="x", pady=1)

    # Timeout label
    timeout_label = tk.Label(
        root, text=f"Auto-slicing with default in {timeout_seconds}s...",
        font=("Segoe UI", 8), bg=bg, fg="#6c7086",
    )
    timeout_label.pack()

    # Countdown
    remaining = [timeout_seconds]

    def countdown():
        if not root.winfo_exists():
            return
        remaining[0] -= 1
        if remaining[0] <= 0:
            on_timeout()
        else:
            timeout_label.config(text=f"Auto-slicing with default in {remaining[0]}s...")
            root.after(1000, countdown)

    root.after(1000, countdown)

    # Buttons
    btn_frame = tk.Frame(root, bg=bg)
    btn_frame.pack(pady=(8, 16))

    cancel_btn = tk.Button(
        btn_frame, text="Skip", command=on_cancel,
        font=("Segoe UI", 10), bg=btn_bg, fg=fg,
        activebackground=btn_hover, activeforeground=fg,
        relief="flat", padx=20, pady=6, cursor="hand2",
    )
    cancel_btn.pack(side="left", padx=8)

    ok_btn = tk.Button(
        btn_frame, text="Slice & Upload", command=on_ok,
        font=("Segoe UI", 10, "bold"), bg=accent, fg="#1e1e2e",
        activebackground="#b4d0fb", activeforeground="#1e1e2e",
        relief="flat", padx=20, pady=6, cursor="hand2",
    )
    ok_btn.pack(side="left", padx=8)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()

    if result["confirmed"]:
        return result["profile"]
    return None


def show_toast(title: str, message: str) -> None:
    """Show a Windows toast notification (non-blocking)."""
    def _notify():
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="PrintForge Auto-Slicer",
                timeout=8,
            )
        except Exception:
            # Fall back to a simple tkinter notification if plyer fails
            try:
                root = tk.Tk()
                root.withdraw()
                root.after(5000, root.destroy)
                from tkinter import messagebox
                messagebox.showinfo(title, message)
            except Exception:
                pass

    thread = threading.Thread(target=_notify, daemon=True)
    thread.start()


if __name__ == "__main__":
    # Test the profile picker
    choice = pick_profile("test_model.stl", default="functional", timeout_seconds=30)
    print(f"Selected: {choice}")

    # Test toast
    if choice:
        show_toast("Auto-Slicer Test", f"You selected: {choice}")
