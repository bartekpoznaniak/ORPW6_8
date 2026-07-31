#!/usr/bin/env python3
"""
orpw4_tx_g24.py - GUI RC/telemetria - wersja g24
Zmiany względem g23-2:
- NOWA sekcja "Oświetlenie" (zwijalna/collapsible), domyślnie ZWINIĘTA
- 41 nowych świateł (Oświetlenie 3-43) w grupach po CH7/CH8/CH14/CH15
  (bity 0-10 na CH7/CH8/CH14, bity 0-7 na CH15 - nadbudówka)
- Zagnieżdżona zwijalna podsekcja "Nadbudówka" (8 świateł, zarezerwowano
  miejsce/logikę do 10 na przyszłość)
- Jeden wspólny slider intensywności z pamięcią wartości per światło
  (na razie TYLKO lokalnie w GUI - RX/STM32 obsługuje póki co ON/OFF,
  wartość intensywności czeka na generyczny system target+value z Etapu 2)
- Wszystko dopisane do JEDNEGO istniejącego CTkScrollableFrame - brak
  zagnieżdżonego, drugiego scrolla
- Reszta (ARM, wieża, FIRE, UART, CRC) bez zmian funkcjonalnych względem g23-2
"""

import customtkinter as ctk
import tkinter as tk
import serial
import struct
from PIL import Image, ImageTk, ImageDraw, ImageFont

CRSF_MIN, CRSF_MAX, CRSF_CTR = 172, 1811, 992
UART_PORT = "/dev/ttyAMA2"
UART_BAUD = 115200
SEND_HZ = 50
FIRE_PULSE_MS = 150

FRAME_SOF = 0xAA
FRAME_EOF = 0xBB
NUM_GUI_CH = 12

DEBUG = False

# ── Helpers ──────────────────────────────────────────────────

def map_crsf(val: float, lo: float, hi: float) -> int:
    r = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    return int(CRSF_MIN + r * (CRSF_MAX - CRSF_MIN))


def build_uart_frame(channels: list) -> bytes:
    payload = struct.pack("<12H", *[max(0, min(2047, v)) for v in channels])
    crc = 0
    for b in payload:
        crc ^= b
    return bytes([FRAME_SOF]) + payload + bytes([crc, FRAME_EOF])


# ── Smooth Toggle (ORYGINAŁ - bez zmian) ─────────────────────
class SmoothToggleSwitch(tk.Canvas):
    def __init__(self, parent, width=60, height=30, command=None):
        raw_bg = parent.cget("fg_color")
        if isinstance(raw_bg, (list, tuple)):
            bg_color = parent._apply_appearance_mode(raw_bg)
        elif str(raw_bg) == "transparent":
            bg_color = parent._apply_appearance_mode(
                ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
            )
        else:
            bg_color = raw_bg

        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg=bg_color,
            cursor="hand2",
        )
        self.width, self.height, self.command = width, height, command
        self.state = False
        self._render()
        self._img_id = self.create_image(0, 0, anchor="nw", image=self._img_off)
        self.bind("<Button-1>", self.toggle)

    def _render(self):
        scale = 4
        sz = int(self.height * scale * 0.28)
        font = None
        for fn in ["arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]:
            try:
                font = ImageFont.truetype(fn, sz)
                break
            except Exception:
                pass
        if not font:
            font = ImageFont.load_default()
        self._img_on = self._make_img(True, font, scale)
        self._img_off = self._make_img(False, font, scale)

    def _make_img(self, state, font, scale):
        w, h = self.width * scale, self.height * scale
        color = "#2e7d32" if state else "#d32f2f"
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, w, h], radius=h // 2, fill=color)
        text = "ON" if state else "OFF"
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx = (w - h) / 2 - tw / 2 if state else h + (w - h) / 2 - tw / 2
        ty = h / 2 - th / 2 - bb[1]
        draw.text((tx, ty), text, fill="white", font=font)
        m = 3 * scale
        d = h - 2 * m
        x0 = (w - h + m) if state else m
        draw.ellipse([x0, m, x0 + d, m + d], fill="white")
        return ImageTk.PhotoImage(
            img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        )

    def toggle(self, _=None):
        self.state = not self.state
        self.itemconfig(
            self._img_id, image=self._img_on if self.state else self._img_off
        )
        if self.command:
            self.command(self.state)

    def set_state(self, state: bool):
        """Ustaw stan programowo (bez emitowania eventu 'toggle')."""
        self.state = state
        self.itemconfig(
            self._img_id, image=self._img_on if self.state else self._img_off
        )


class FireModeSelector(ctk.CTkFrame):
    def __init__(self, parent, command=None):
        super().__init__(parent, fg_color="transparent")
        self.value = 0
        self.command = command
        self.grid_columnconfigure(1, weight=1)

        self.btn_up = ctk.CTkButton(self, text="↑", width=30, command=self._inc)
        self.btn_up.grid(row=0, column=0, padx=2)

        self.label = ctk.CTkLabel(self, text="0", width=30)
        self.label.grid(row=0, column=1)

        self.btn_down = ctk.CTkButton(self, text="↓", width=30, command=self._dec)
        self.btn_down.grid(row=0, column=2, padx=2)

    def _inc(self):
        if self.value < 9:
            self.value += 1
            self._update()

    def _dec(self):
        if self.value > 0:
            self.value -= 1
            self._update()

    def _update(self):
        self.label.configure(text=str(self.value))
        if self.command:
            self.command(self.value)


# ── SystemRow (bez zmian funkcjonalnych) ──────────────────────
class SystemRow(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        name,
        has_slider=False,
        has_button=False,
        has_switch=True,
        min_val=0,
        max_val=100,
        unit="%",
        callback=None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.name, self.callback, self.unit = name, callback, unit
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=name, font=("Arial", 13, "bold"), width=160, anchor="w"
        ).grid(row=0, column=0, padx=(10, 5), pady=4)

        self.slider = None
        if has_slider:
            cont = ctk.CTkFrame(self, fg_color="transparent")
            cont.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
            cont.grid_columnconfigure(0, weight=1)
            self.slider = ctk.CTkSlider(
                cont, from_=min_val, to=max_val, command=self._slider_moved
            )
            self.slider.grid(row=0, column=0, sticky="ew")
            self.slider.set(min_val)
            self._val_lbl = ctk.CTkLabel(
                cont, text=f"{min_val}{unit}", font=("Arial", 10), width=50
            )
            self._val_lbl.grid(row=0, column=1, padx=(5, 0))
        else:
            ctk.CTkFrame(self, fg_color="transparent", height=0).grid(row=0, column=1)

        self.switch = None
        if has_switch:
            self.switch = SmoothToggleSwitch(
                self, width=60, height=30, command=self._on_change
            )
            self.switch.grid(row=0, column=2, padx=10, pady=4)
        else:
            ctk.CTkFrame(self, width=60, height=30, fg_color="transparent").grid(
                row=0, column=2
            )

        self.btn = None
        self.fire_selector = None

        if has_button:
            if name == "Procedura Ognia":
                self.fire_selector = FireModeSelector(
                    self,
                    command=lambda v: self.callback("Procedura Ognia_MODE", False, v),
                )
                self.fire_selector.grid(row=0, column=3, padx=(5, 5), pady=4)
                fire_col = 4
            else:
                fire_col = 3

            self.btn = ctk.CTkButton(
                self,
                text="FIRE",
                command=self._on_impulse,
                fg_color="#b71c1c",
                hover_color="#f44336",
                font=("Arial", 12, "bold"),
                width=80,
                height=30,
            )
            self.btn.grid(row=0, column=fire_col, padx=(5, 10), pady=4)
        else:
            ctk.CTkFrame(self, width=80, height=30, fg_color="transparent").grid(
                row=0, column=3
            )

    def _slider_moved(self, val):
        if hasattr(self, "_val_lbl"):
            self._val_lbl.configure(text=f"{int(val)}{self.unit}")
        self._on_change()

    def _on_impulse(self):
        if self.callback:
            self.callback(self.name, False, "IMPULSE")

    def _on_change(self, _=None):
        if self.callback:
            sw = self.switch.state if self.switch else False
            val = int(self.slider.get()) if self.slider else None
            self.callback(self.name, sw, val)


# ── NOWE: CollapsibleSection ───────────────────────────────────
class CollapsibleSection(ctk.CTkFrame):
    """Nagłówek klikalny + zawartość pokazywana/skrywana przez pack/pack_forget.
    Nie tworzy WŁASNEGO scrolla - żyje wewnątrz istniejącego CTkScrollableFrame."""

    def __init__(self, parent, title, expanded=False, header_extra=None,
                 indent=0, header_font=("Arial", 13, "bold")):
        super().__init__(parent, fg_color="transparent")
        self.expanded = expanded
        self.title_text = title

        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=(indent, 0))

        self.arrow_lbl = ctk.CTkLabel(
            self.header,
            text=self._arrow_text(),
            font=header_font,
            anchor="w",
            cursor="hand2",
        )
        self.arrow_lbl.pack(side="left", padx=(10, 5), pady=6)
        self.arrow_lbl.bind("<Button-1>", self.toggle)
        self.header.bind("<Button-1>", self.toggle)

        # miejsce na dodatkowe widgety w headerze (np. master slider)
        self.header_extra_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        self.header_extra_frame.pack(side="left", fill="x", expand=True, padx=5)
        if header_extra:
            header_extra(self.header_extra_frame)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        if self.expanded:
            self.body.pack(fill="x", padx=(indent, 0))

    def _arrow_text(self):
        return ("▼ " if self.expanded else "▶ ") + self.title_text

    def toggle(self, _=None):
        self.expanded = not self.expanded
        self.arrow_lbl.configure(text=self._arrow_text())
        if self.expanded:
            self.body.pack(fill="x", padx=0)
        else:
            self.body.pack_forget()


# ── NOWE: LightRow - jeden wiersz światła ──────────────────────
class LightRow(ctk.CTkFrame):
    def __init__(self, parent, number, on_switch, on_select):
        super().__init__(parent, fg_color="transparent")
        self.number = number
        self.name = f"Oświetlenie {number}"
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(
            self, text=self.name, anchor="w", font=("Arial", 12), cursor="hand2"
        )
        self.label.grid(row=0, column=0, sticky="ew", padx=(10, 5), pady=2)
        self.label.bind("<Button-1>", lambda e: on_select(number))

        self.switch = SmoothToggleSwitch(
            self, width=50, height=24,
            command=lambda st: on_switch(number, st),
        )
        self.switch.grid(row=0, column=1, padx=10, pady=2)

    def highlight(self, active: bool):
        self.configure(fg_color=("gray25" if active else "transparent"))


# ── NOWE: LightingPanel - cała sekcja "Oświetlenie" ────────────
class LightingPanel(ctk.CTkFrame):
    """
    41 nowych świateł (numery 3-43) rozłożonych na CH7/CH8/CH14/CH15:
      CH7  (gui_ch idx=2)  -> światła 3-13   (11 szt., bity 0-10)
      CH8  (gui_ch idx=3)  -> światła 14-24  (11 szt., bity 0-10)
      CH14 (gui_ch idx=9)  -> światła 25-35  (11 szt., bity 0-10)
      CH15 (gui_ch idx=10) -> światła 36-43  (nadbudówka, 8 szt., bity 0-7)
        (zapas do 10 zarezerwowany logicznie, na razie tylko 8 aktywnych)

    Wspólny slider intensywności trzyma wartość TYLKO lokalnie
    (self.light_values) - RX/STM32 obsługuje aktualnie ON/OFF (CAN 0x150-0x187),
    wartość analogowa czeka na generyczny system target+value (Etap 2).
    """

    MAIN_GROUPS = [
        (2, 3, 11),    # (gui_ch idx dla CH7, pierwszy numer światła, ilość)
        (3, 14, 11),   # CH8
        (9, 25, 11),   # CH14
    ]
    NADBUDOWKA_GROUP = (10, 36, 8)  # CH15, światła 36-43

    def __init__(self, parent, set_bit_cb, master_send_cb):
        super().__init__(parent, fg_color="transparent")
        self.set_bit_cb = set_bit_cb          # (ch_idx, bit, state) -> None
        self.master_send_cb = master_send_cb  # wywoływane po zmianie slidera

        self.light_values = {}   # numer_swiatla -> intensywność (0-100), lokalnie
        self.light_meta = {}     # numer_swiatla -> (ch_idx, bit)
        self.rows = {}           # numer_swiatla -> LightRow
        self.active_number = None

        for ch_idx, first, count in self.MAIN_GROUPS:
            for bit in range(count):
                num = first + bit
                self.light_meta[num] = (ch_idx, bit)
                self.light_values[num] = 0

        nb_ch, nb_first, nb_count = self.NADBUDOWKA_GROUP
        for bit in range(nb_count):
            num = nb_first + bit
            self.light_meta[num] = (nb_ch, bit)
            self.light_values[num] = 0

        # ── Sekcja główna "Oświetlenie" ──
        self.section = CollapsibleSection(
            self, "Oświetlenie (3-43)", expanded=False,
            header_extra=self._build_master_slider,
        )
        self.section.pack(fill="x", pady=2)

        body = self.section.body

        main_numbers = [n for ch_idx, first, count in self.MAIN_GROUPS
                        for n in range(first, first + count)]
        for num in main_numbers:
            row = LightRow(body, num, self._on_switch, self._on_select)
            row.pack(fill="x")
            self.rows[num] = row

        # ── Zagnieżdżona podsekcja "Nadbudówka" ──
        self.nadbudowka_section = CollapsibleSection(
            body, "Nadbudówka (8/10 zarezerwowane)", expanded=False, indent=20,
        )
        self.nadbudowka_section.pack(fill="x", pady=(4, 0))
        for num in range(nb_first, nb_first + nb_count):
            row = LightRow(self.nadbudowka_section.body, num,
                            self._on_switch, self._on_select)
            row.pack(fill="x")
            self.rows[num] = row

    def _build_master_slider(self, parent_frame):
        ctk.CTkLabel(parent_frame, text="Intensywność:", font=("Arial", 11)).pack(
            side="left", padx=(5, 5)
        )
        self.master_slider = ctk.CTkSlider(
            parent_frame, from_=0, to=100, command=self._on_master_slider
        )
        self.master_slider.set(0)
        self.master_slider.pack(side="left", fill="x", expand=True, padx=5)
        self.active_lbl = ctk.CTkLabel(
            parent_frame, text="(brak)", font=("Arial", 10), width=90
        )
        self.active_lbl.pack(side="left", padx=(5, 10))

    def _on_select(self, number):
        self.active_number = number
        self.master_slider.set(self.light_values[number])
        self.active_lbl.configure(text=f"Oświetlenie {number}")
        for n, row in self.rows.items():
            row.highlight(n == number)

    def _on_switch(self, number, state):
        ch_idx, bit = self.light_meta[number]
        self.set_bit_cb(ch_idx, bit, state)
        # klik przełącznika też aktywuje slider dla tego światła
        self._on_select(number)

    def _on_master_slider(self, val):
        if self.active_number is None:
            return
        self.light_values[self.active_number] = int(val)
        self.active_lbl.configure(
            text=f"Oświetlenie {self.active_number} ({int(val)}%)"
        )
        # UWAGA: wartość na razie NIE jest wysyłana przez CRSF/CAN -
        # RX/STM32 obsługuje tylko ON/OFF. Zostaje w self.light_values
        # jako przygotowanie do generycznego systemu target+value (Etap 2).
        if self.master_send_cb:
            self.master_send_cb(self.active_number, int(val))


# ── Main App ─────────────────────────────────────────────────
class App(ctk.CTk):

    SYSTEMS = [
        ("ARM", False, False, True, 0, 1, ""),
        ("Oświetlenie 1", False, False, True, 0, 1, ""),
        ("Oświetlenie 2", False, False, True, 0, 1, ""),
        ("Obrót Wieży", True, False, True, -180, 180, "°"),
        ("Elewacja Działa", True, False, True, -20, 90, "°"),
        ("Wysunięcie Lufy", True, False, True, 0, 500, "mm"),
        ("Moc Strzału", True, False, True, 0, 100, "%"),
        ("Procedura Ognia", False, True, False, 0, 0, ""),
    ]

    ARM_IDX = 0

    SWITCH_MAP = {
        "Oświetlenie 1": (1, 1),
        "Oświetlenie 2": (1, 2),
        "Obrót Wieży": (1, 3),
        "Elewacja Działa": (1, 4),
        "Wysunięcie Lufy": (1, 5),
        "Moc Strzału": (1, 6),
    }

    SLIDER_MAP = {
        "Obrót Wieży": (4, -180, 180),
        "Elewacja Działa": (5, -20, 90),
        "Wysunięcie Lufy": (6, 0, 500),
        "Moc Strzału": (7, 0, 100),
    }

    FIRE_MAP = {
        "Procedura Ognia": (8, 1),
    }

    def __init__(self):
        super().__init__()
        self.title("Military Control Panel 2026 - g24")
        self.geometry("860x620")

        self._gui_ch = [CRSF_CTR] * NUM_GUI_CH
        self.fire_mode = 0
        self._gui_ch[self.ARM_IDX] = CRSF_MIN

        # bitmaski startowe = 0
        self._gui_ch[1] = 0   # CH6  - Oświetlenie1-2 + wieża-enable x4
        self._gui_ch[2] = 0   # CH7  - Oświetlenie 3-13
        self._gui_ch[3] = 0   # CH8  - Oświetlenie 14-24
        self._gui_ch[8] = 0   # CH13 - fire bitmask
        self._gui_ch[9] = 0   # CH14 - Oświetlenie 25-35   (NOWE)
        self._gui_ch[10] = 0  # CH15 - Oświetlenie 36-43   (NOWE, nadbudówka)
        # CH16 (idx 11) - jedyny wolny kanał zapasowy, zostaje CRSF_CTR

        try:
            self._ser = serial.Serial(
                UART_PORT, UART_BAUD, timeout=0.01, write_timeout=0.01
            )
            self._ser.reset_output_buffer()
            print(f"[UART] OK {UART_PORT}")
        except serial.SerialException as e:
            self._ser = None
            print(f"[UART] ERROR {e}")

        ctk.CTkLabel(
            self, text="⚙ PANEL STEROWANIA - RC ELRS 2026 (g24)",
            font=("Arial", 16, "bold"),
        ).pack(pady=8)

        self._frame = ctk.CTkScrollableFrame(self, width=820, height=520)
        self._frame.pack(padx=16, pady=4, fill="both", expand=True)

        for name, sl, btn, sw, mi, ma, unit in self.SYSTEMS:
            SystemRow(
                self._frame, name, sl, btn, sw, mi, ma, unit,
                callback=self._on_event,
            ).pack(fill="x", pady=2)

        # NOWE: panel oświetlenia dopisany do TEGO SAMEGO scrolla
        self.lighting_panel = LightingPanel(
            self._frame,
            set_bit_cb=self._set_light_bit,
            master_send_cb=self._on_light_intensity,
        )
        self.lighting_panel.pack(fill="x", pady=(8, 2))

        self._send_loop()

    def _on_event(self, name: str, state: bool, value):
        if name == "Procedura Ognia_MODE":
            self.fire_mode = value
            return
        if name == "ARM":
            self._gui_ch[self.ARM_IDX] = CRSF_MAX if state else CRSF_MIN
            return

        if name in self.SWITCH_MAP:
            ch_idx, bit = self.SWITCH_MAP[name]
            if state:
                self._gui_ch[ch_idx] |= 1 << bit
            else:
                self._gui_ch[ch_idx] &= ~(1 << bit)

        if name in self.SLIDER_MAP and value not in (None, "IMPULSE"):
            ch_idx, lo, hi = self.SLIDER_MAP[name]
            if state:
                self._gui_ch[ch_idx] = map_crsf(float(value), lo, hi)

        if value == "IMPULSE" and name in self.FIRE_MAP:
            ch_idx, bit = self.FIRE_MAP[name]
            self._gui_ch[ch_idx] = (self.fire_mode << 2) | (1 << bit)
            self._send_now()
            self.after(FIRE_PULSE_MS, lambda: self._clear_fire(ch_idx, bit))

        print("MODE:", self.fire_mode)

    def _set_light_bit(self, ch_idx: int, bit: int, state: bool):
        """Callback z LightingPanel - ustawia/zeruje bit na CH7/CH8/CH14/CH15."""
        if state:
            self._gui_ch[ch_idx] |= 1 << bit
        else:
            self._gui_ch[ch_idx] &= ~(1 << bit)

    def _on_light_intensity(self, number: int, value: int):
        """Na razie tylko log/hook - RX obsługuje ON/OFF, wartość czeka na Etap 2."""
        if DEBUG:
            print(f"[LIGHT INTENSITY] Oświetlenie {number} -> {value}% (lokalnie)")

    def _clear_fire(self, ch_idx: int, bit: int):
        self._gui_ch[ch_idx] &= ~(1 << bit)

    def _send_now(self):
        if not self._ser:
            return
        try:
            frame = build_uart_frame(self._gui_ch)
            self._ser.write(frame)
            self._ser.flush()
            if DEBUG:
                print(frame.hex())
        except serial.SerialException as e:
            print(f"[UART WRITE ERROR] {e}")

    def _send_loop(self):
        self._send_now()
        self.after(1000 // SEND_HZ, self._send_loop)


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = App()
    app.mainloop()
