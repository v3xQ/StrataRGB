class RGBColor:
    def __init__(self, red, green, blue):
        self.red = red
        self.green = green
        self.blue = blue

    def __repr__(self):
        return f"RGBColor({self.red}, {self.green}, {self.blue})"
