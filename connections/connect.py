import board
import busio
from digitalio import DigitalInOut
import adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi

# Get wifi details and more from a secrets.py file
def connect():
    try:
        from secrets import secrets
    except ImportError:
        print("Wifi credentials not found")
        raise

    #  ESP32 pins
    esp32_cs = DigitalInOut(board.CS1)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)

    #  uses the secondary SPI connected through the ESP32
    spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)

    esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

    requests.set_socket(socket, esp)

    while not esp.is_connected:
        try:
            esp.connect_AP(secrets["ssid"], secrets["password"])
        except RuntimeError as e:
            print("could not connect to AP, retrying: ", e)
            continue
    print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi, "IP:", esp.pretty_ip(esp.ip_address))