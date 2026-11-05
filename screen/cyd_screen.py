"""
Future Screen — turns the CYD into a small USB second display for Windows.

    pip install pillow pyserial
    python cyd_screen.py --port COM3

Options:
    --port COM3        serial port of the CYD (Device Manager -> Ports)
    --fps 4            frames per second to try (921600 baud allows ~3-4)
    --rotate 90        turn the picture 90 degrees (use when the CYD lies on its side)
    --region 0,0,1920,1080   capture only this part of the screen

How it works: the screen is grabbed, scaled to 320x240, turned into 16-bit
colour, compressed with a simple run-length code and pushed over the USB cable.
The CYD draws it and keeps showing the last frame.
"""
import argparse
import hashlib
import struct
import sys
import time

try:
    from PIL import ImageGrab, Image
except ImportError:
    print("Missing Pillow. Run:  pip install pillow")
    sys.exit(1)

try:
    import serial
except ImportError:
    print("Missing pyserial. Run:  pip install pyserial")
    sys.exit(1)

W, H = 240, 320          # the CYD panel as the firmware drives it (portrait)
MAGIC = b"\xAA\x55"


def to_rgb565(img):
    """PIL image -> list of 16-bit colours in row order"""
    img = img.convert("RGB")
    px = list(img.getdata())
    out = []
    for r, g, b in px:
        out.append(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))
    return out


def rle(colours):
    """[(colour, count), ...] -> the byte string the CYD expects"""
    out = bytearray()
    if not colours:
        return bytes(out)
    cur = colours[0]
    n = 0
    for c in colours:
        if c == cur and n < 0xFFFF:
            n += 1
        else:
            out += struct.pack("<HH", cur, n)
            cur = c
            n = 1
    out += struct.pack("<HH", cur, n)
    return bytes(out)


def frame_bytes(img):
    payload = rle(to_rgb565(img))
    if len(payload) > 26000:                 # too busy: fewer colours -> longer runs
        quant = img.convert("RGB").quantize(colors=8, method=2).convert("RGB")
        payload = rle(to_rgb565(quant))
    if len(payload) > 29000:                 # still huge: send a plain grey frame
        payload = rle([0x2104] * (W * H))
    return MAGIC + struct.pack("<H", len(payload)) + payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="e.g. COM3")
    ap.add_argument("--fps", type=float, default=4.0)
    ap.add_argument("--rotate", type=int, default=0, choices=[0, 90])
    ap.add_argument("--region", default="", help="x,y,w,h  (default: whole screen)")
    a = ap.parse_args()

    box = None
    if a.region:
        try:
            box = tuple(int(v) for v in a.region.split(","))
            assert len(box) == 4
        except Exception:
            print("--region needs four numbers: x,y,w,h")
            sys.exit(1)

    ser = serial.Serial(a.port, 921600, timeout=1, write_timeout=3)
    time.sleep(1.5)
    print("connected to", a.port, "- press Ctrl+C to stop")

    target = 1.0 / max(a.fps, 0.2)
    last_hash = None
    sent = 0
    t0 = time.time()

    while True:
        start = time.time()
        try:
            grab = ImageGrab.grab(bbox=box, all_screens=not box)
        except TypeError:
            grab = ImageGrab.grab()
        img = grab
        if a.rotate == 90:
            img = img.rotate(-90, expand=True)     # CYD lying on its side
        img = img.resize((W, H), Image.BILINEAR)

        data = frame_bytes(img)
        h = hashlib.md5(data).digest()
        if h != last_hash:                      # skip identical frames
            last_hash = h
            ser.write(data)
            ser.flush()
            sent += 1

        fps = sent / max(time.time() - t0, 0.001)
        sys.stdout.write("\rframe %d  %.1f fps  %.1f KB/frame   " %
                         (sent, fps, len(data) / 1024.0))
        sys.stdout.flush()

        wait = target - (time.time() - start)
        if wait > 0:
            time.sleep(wait)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
    except serial.SerialException as e:
        print("\nSerial error:", e)
        print("Check the COM number in Device Manager and that the cable is connected.")
