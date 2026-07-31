
import customtkinter as ctk

app = ctk.CTk()

for name in ["ARM", "SW1", "SW2"]:

    row = ctk.CTkFrame(app)
    row.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(row, text=name).grid(row=0, column=0, sticky="w")
    ctk.CTkSwitch(row, text="").grid(row=0, column=1, padx=20)

app.mainloop()
