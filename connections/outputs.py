from connections.Kasa import SmartPowerStrip
import time
import board
from digitalio import DigitalInOut, Direction, Pull
from connections.inputs import soil_sense 

# creates class for a water pump to run safely
# strip = SmartPowerStrip object that the pump is plugged into
# plug_num = plug number on the strip
# switch = initialized switch to digital pin
# the switch is used to detect if the water level is sufficient to run
# boolean value if true then runs


class pump(object):

    def __init__(self, strip, plug_num, switch, sensor):
        self.strip = strip
        self.plug_num = plug_num
        self.switch = switch
        self.value = self.switch.value
        self.sensor = sensor

    # runs pump for i amount of seconds
    # checks switch value every second
    # if switch goes to false the sends off command
    def run(self, delay):
        
        self.value = self.switch.value
        if not self.value:
            print(f"Water level to low for pump")
            return False

        i = delay
        self.strip.timed_toggle('on', plug_num=self.plug_num, delay= i)
        print(f"pump ON: Watering for {i} seconds")

        while (self.value and i > 0):
            time.sleep(1)
            i = i-1
            print(f"{i} seconds, {self.sensor.status()}")
            self.value = self.switch.value
            dry, moisture = self.sensor.status(watering=True)
            if not self.value:
                self.strip.toggle_plug('off', plug_num= self.plug_num)
                print(f"Watering Complete: Ran out of water at {delay-i} seconds")
                return False
            elif not dry:
                self.strip.toggle_plug('off', plug_num= self.plug_num)
                print(f"Watering Complete: Plant at {moisture}")
                return True
        print(f"Watering Complete: ran {delay} seconds")
        return True
    