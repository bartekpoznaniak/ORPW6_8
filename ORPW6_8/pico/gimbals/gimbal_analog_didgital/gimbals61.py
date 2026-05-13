import machine
import time
from ads1x15 import ADS1115

# Inicjalizacja I2C (100kHz dla stabilności na długich kablach gimbali)

i2c = machine.I2C(0, sda=machine.Pin(0), scl=machine.Pin(1), freq=100000)

print("Skanowanie szyny I2C...")
devices = i2c.scan()

if not devices:
    print("BŁĄD: Nie znaleziono żadnego urządzenia I2C!")
    print("Sprawdź zasilanie (3.3V) i kable SDA/SCL.")
    raise SystemExit # Zatrzymuje skrypt

# Pobieramy pierwszy znaleziony adres (np. 0x48 lub 0x49)
ads_address = devices[0]
print(f"Wykryto urządzenie pod adresem: {hex(ads_address)}")

# Inicjalizacja ADS1115 z automatycznie wykrytym adresem
ads = ADS1115(i2c, address=ads_address, gain=1)

print("-" * 60)
print("Odczyt gimbali (A0-A3) aktywny... (Ctrl+C przerywa)")
print("-" * 60)

while True:
    try:
        # Odczyt kanałów z pauzami 5ms (bezpieczne dla gimbali)
        raw0 = ads.read(4, 0)
        time.sleep_ms(5)
        raw1 = ads.read(4, 1)
        time.sleep_ms(5)
        raw2 = ads.read(4, 2)
        time.sleep_ms(5)
        raw3 = ads.read(4, 3)

        # Konwersja na wolty
        v0 = raw0 * (4.096 / 32768)
        v1 = raw1 * (4.096 / 32768)
        v2 = raw2 * (4.096 / 32768)
        v3 = raw3 * (4.096 / 32768)

        # Odświeżanie w jednej linii (\r na początku, end="" na końcu)
        # Dodano stałą szerokość pól, żeby tekst nie "skakał"
        out = f"\rA0:{v0:5.2f}V | A1:{v1:5.2f}V | A2:{v2:5.2f}V | A3:{v3:5.2f}V | R0:{raw0:5d}"
        print(out, end="")

        time.sleep_ms(30) # Odświeżanie ok. 30 razy na sekundę
        
    except Exception as e:
        print(f"\nBłąd komunikacji: {e}")
        time.sleep(1)
