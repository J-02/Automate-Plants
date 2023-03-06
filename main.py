import time
import board
from digitalio import DigitalInOut, Direction, Pull
from analogio import AnalogIn
from connections.outputs import pump
from connections.inputs import soil_sense
from connections.Kasa import SmartPowerStrip

def main():

    strip = SmartPowerStrip("192.168.0.111")

    switch1 = DigitalInOut(board.D2)
    switch1.direction = Direction.INPUT
    switch1.pull = Pull.UP
    water_availble = switch1.value
    soil_moisture = soil_sense(AnalogIn(board.A0), 500, 400)
    water_pump = pump(strip, 3, switch1, soil_moisture)
    
    while True:
        
        water_availble = switch1.value
        dry, moisture = soil_moisture.status()

        if water_availble and dry:
            water_availble = water_pump.run(10)
        time.sleep(2.5)