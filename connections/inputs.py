from analogio import AnalogIn


class soil_sense(object):

    def __init__(self, pin, upper=520, lower=400):
        self.pin = pin
        self.value = self.pin.value
        self.upper = upper
        self.lower = lower

    def status(self,  watering=False):
        moisture = self.update() / 100
        if watering:
            if moisture < self.lower:
                dry = False
            else: dry = True
        else:
            if moisture > self.upper:
                dry = True
            else: dry = False
        print(f"{moisture}: dry = {dry}")
        return dry, moisture

    def update(self):
        self.value = self.pin.value
        return self.value