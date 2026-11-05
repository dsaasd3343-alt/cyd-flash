"""
Future Keyboard — computer side.
Run this on the Windows PC; the phone app types into whatever window is focused.

    python future_keyboard.py

No extra packages needed. Stop with Ctrl+C.
"""
import socket
import ctypes
import sys
import time

PORT = 8765

# ---------------- Windows key injection ----------------
user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK = {
    "ENTER": 0x0D, "TAB": 0x09, "BACKSPACE": 0x08, "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "DEL": 0x2E, "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "DELETE": 0x2E,
    "WIN": 0x5B, "CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def _send(vk=0, scan=0, flags=0):
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def tap(vk):
    _send(vk=vk, flags=0)
    _send(vk=vk, flags=KEYEVENTF_KEYUP)


def type_text(text):
    """types any unicode text, Arabic included"""
    for ch in text:
        code = ord(ch)
        if code > 0xFFFF:                     # emoji and other astral chars
            code -= 0x10000
            hi = 0xD800 + (code >> 10)
            lo = 0xDC00 + (code & 0x3FF)
            for unit in (hi, lo):
                _send(scan=unit, flags=KEYEVENTF_UNICODE)
                _send(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
            continue
        _send(scan=code, flags=KEYEVENTF_UNICODE)
        _send(scan=code, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)


MODS = {"CTRL": VK["CTRL"], "SHIFT": VK["SHIFT"], "ALT": VK["ALT"], "WIN": VK["WIN"]}


def do_key(spec):
    parts = [p.strip().upper() for p in spec.split("+") if p.strip()]
    if not parts:
        return
    mods, base = [], None
    for p in parts:
        if p in MODS and (base is None or p != parts[-1]):
            mods.append(MODS[p])
        else:
            base = p
    if base is None:                          # only modifiers, e.g. "CTRL"
        base = parts[-1]
    for m in mods:
        _send(vk=m, flags=0)
    time.sleep(0.01)
    if base in VK:
        tap(VK[base])
    elif len(base) == 1:
        _send(vk=ord(base.upper()), flags=0)
        _send(vk=ord(base.upper()), flags=KEYEVENTF_KEYUP)
    time.sleep(0.01)
    for m in reversed(mods):
        _send(vk=m, flags=KEYEVENTF_KEYUP)


def do_scroll(amount):
    # mouse wheel: keep the cursor where it is, just wheel
    MOUSEEVENTF_WHEEL = 0x0800
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(amount) * 120, 0)


def handle(line):
    if line == "HELLO":
        print("  phone connected")
        return
    if line.startswith("T:"):
        type_text(line[2:].replace("\\n", "\n"))
    elif line.startswith("K:"):
        do_key(line[2:])
    elif line.startswith("S:"):
        do_scroll(line[2:])


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(1)
    print("=" * 46)
    print("  Future Keyboard — ready")
    print("  Type this IP in the phone app: " + local_ip())
    print("  Port: %d     (Ctrl+C to stop)" % PORT)
    print("=" * 46)
    while True:
        conn, addr = srv.accept()
        print("connected: %s" % (addr[0],))
        buf = b""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    txt = line.decode("utf-8", "ignore").strip()
                    if txt:
                        handle(txt)
        except Exception as e:
            print("link closed:", e)
        finally:
            conn.close()
            print("disconnected — waiting again")


if __name__ == "__main__":
    if not sys.platform.startswith("win"):
        print("This server injects keys with the Windows API — run it on the PC.")
    main()
