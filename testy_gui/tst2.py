import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont


class SmoothToggleSwitch(tk.Canvas):
    def __init__(self, parent, width=60, height=30, command=None):

        raw_bg = parent.cget("fg_color")

        if isinstance(raw_bg, (list, tuple)):
            bg_color = parent._apply_appearance_mode(raw_bg)
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

        self.width = width
        self.height = height
        self.command = command
        self.state = False

        self._render()

        self._img_id = self.create_image(
            0, 0, anchor="nw", image=self._img_off
        )

        self.bind("<Button-1>", self.toggle)

    def _render(self):

        scale = 4

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(self.height))
        except:
            font = ImageFont.load_default()

        self._img_on = self._make_img(True, font, scale)
        self._img_off = self._make_img(False, font, scale)

    def _make_img(self, state, font, scale):

        w = self.width * scale
        h = self.height * scale

        color = "#2e7d32" if state else "#d32f2f"

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [0, 0, w, h],
            radius=h // 2,
            fill=color,
        )

        text = "ON" if state else "OFF"

        bb = draw.textbbox((0, 0), text, font=font)

        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]

        tx = (w - h) / 2 - tw / 2 if state else h + (w - h) / 2 - tw / 2
        ty = h / 2 - th / 2 - bb[1]

        draw.text((tx, ty), text, fill="white", font=font)

        m = 3 * scale
        d = h - 2 * m

        x0 = (w - h + m) if state else m

        draw.ellipse(
            [x0, m, x0 + d, m + d],
            fill="white"
        )

        return ImageTk.PhotoImage(
            img.resize(
                (self.width, self.height),
                Image.Resampling.LANCZOS
            )
        )

    def toggle(self, event=None):

        self.state = not self.state

        self.itemconfig(
            self._img_id,
            image=self._img_on if self.state else self._img_off
        )

        if self.command:
            self.command(self.state)


ctk.set_appearance_mode("dark")

app = ctk.CTk()
app.geometry("400x220")

for name in ["ARM", "Oświetlenie 1", "Oświetlenie 2", "Pierdolenie o szopenie" ]:

    row = ctk.CTkFrame(app)
    row.pack(fill="x", padx=10, pady=5)

    ctk.CTkLabel(
        row,
        text=name,
        width=150,
        anchor="w"
    ).pack(side="left", padx=10)

    SmoothToggleSwitch(
        row,
        width=80,
        height=40
    ).pack(side="right", padx=(10,50))

app.mainloop()





# też ciekawe 

# to ciekwe z krótszymi odstępami

#for name in ["ARM", "Oświetlenie 1", "Oświetlenie 2"]:
#
#    row = ctk.CTkFrame(app, height=50)
#    row.pack(anchor="w", padx=10, pady=5)
#
#    ctk.CTkLabel(
#        row,
#        text=name
#    ).grid(row=0, column=0, padx=(10, 20), pady=5)
#
#    SmoothToggleSwitch(
#        row,
#        width=80,
#        height=40
#    ).grid(row=0, column=1, padx=(0, 10), pady=5)
