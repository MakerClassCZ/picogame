class PWMAudioOut:
    def __init__(self, pin=None): pass
    def play(self, sample, loop=False): pass
    def stop(self): pass
    def deinit(self): pass                  # CP releases the pin; nothing to free here
