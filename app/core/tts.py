import queue
import threading

from app.data.config import Config


_PHRASES = {
    "shoot": "shoot now",
    "heal": "heal up",
    "complete": "test complete",
    "update": "update available",
}


def _make_engine():
    # Bypass pyttsx3's per-thread cache to get a completely fresh engine each call.
    # Reusing the same engine across runAndWait() calls causes SAPI5 to hang on Windows.
    from pyttsx3 import engine as _e
    return _e.Engine(None, False)


class TTSEngine:
    def __init__(self, config: Config):
        self._config = config
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            text, volume, voice_id = item
            try:
                engine = _make_engine()
                engine.setProperty("volume", float(volume))
                if voice_id:
                    engine.setProperty("voice", voice_id)
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

    def speak(self, text: str):
        self._queue.put((text, self._config.tts_volume, self._config.tts_voice))

    def speak_event(self, event: str, **kwargs):
        if not self._config.tts_enabled:
            return
        if not self._config.tts_events.get(event, False):
            return
        if event == "recorded":
            damage = kwargs.get("damage", 0)
            hp = kwargs.get("hp", 0)
            if self._config.tts_events.get("recorded_hp", True) and hp:
                text = f"{damage} percent, {hp} health points"
            else:
                text = f"recorded, {damage} percent"
        else:
            text = _PHRASES.get(event)
            if text is None:
                return
        self.speak(text)

    def get_available_voices(self) -> list[dict]:
        try:
            engine = _make_engine()
            voices = engine.getProperty("voices")
            return [{"id": v.id, "name": v.name} for v in voices]
        except Exception:
            return []

    def reload_config(self):
        pass
