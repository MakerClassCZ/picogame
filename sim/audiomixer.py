class _Voice:
    level = 1.0
    playing = False
    def play(self, s, loop=False): pass
    def stop(self): pass
class Mixer:
    def __init__(self, voice_count=4, **kw):
        self.voice = [_Voice() for _ in range(voice_count)]
