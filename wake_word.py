"""
Wake Word Detection — Cross-platform "Hey Jarvis" listener.
Uses Vosk (offline, free) for wake word detection.
No microphone clicking needed — always listening in background.

Setup:
    pip install vosk sounddevice
    Download a small Vosk model from https://alphacephei.com/vosk/models
    e.g. vosk-model-small-en-us-0.15  -> unzip into jarvis/models/vosk-model

Required .env vars:
    WAKE_WORD=hey jarvis          (the phrase to listen for)
    VOSK_MODEL_PATH=models/vosk-model  (path to the Vosk model folder)
    WAKE_WORD_SENSITIVITY=0.7     (0.0 - 1.0, higher = stricter matching)
"""

import json
import logging
import os
import threading
import queue
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("jarvis.wake_word")

WAKE_WORD = os.getenv("WAKE_WORD", "hey jarvis").lower()
VOSK_MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model")
SAMPLE_RATE = 16000
BLOCK_SIZE = 8000


class WakeWordDetector:
    """
    Always-on background listener that fires a callback when
    the wake word is detected.
    """

    def __init__(self, on_wake: Callable[[], None]):
        self.on_wake = on_wake
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._model = None
        self._recognizer = None
        self._cooldown = False  # prevent double-triggers

    def _load_model(self) -> bool:
        """Load the Vosk model. Returns True if successful."""
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError:
            log.error(
                "Vosk not installed. Run: pip install vosk sounddevice\n"
                "Then download a model from https://alphacephei.com/vosk/models"
            )
            return False

        model_path = Path(VOSK_MODEL_PATH)
        if not model_path.exists():
            log.error(
                f"Vosk model not found at {VOSK_MODEL_PATH}.\n"
                "Download from https://alphacephei.com/vosk/models and unzip into models/vosk-model"
            )
            return False

        from vosk import Model, KaldiRecognizer
        self._model = Model(str(model_path))
        self._recognizer = KaldiRecognizer(self._model, SAMPLE_RATE)
        log.info(f"Vosk model loaded from {model_path}. Listening for: '{WAKE_WORD}'")
        return True

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            log.debug(f"Audio status: {status}")
        self._audio_queue.put(bytes(indata))

    def _listen_loop(self):
        """Main detection loop — runs in background thread."""
        try:
            import sounddevice as sd
        except ImportError:
            log.error("sounddevice not installed. Run: pip install sounddevice")
            return

        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                log.info(f"Wake word detection active. Say '{WAKE_WORD}' to activate JARVIS.")
                while self._running:
                    try:
                        data = self._audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if self._recognizer.AcceptWaveform(data):
                        result = json.loads(self._recognizer.Result())
                        text = result.get("text", "").lower()
                    else:
                        partial = json.loads(self._recognizer.PartialResult())
                        text = partial.get("partial", "").lower()

                    if WAKE_WORD in text and not self._cooldown:
                        log.info(f"Wake word detected: '{text}'")
                        self._cooldown = True
                        # Fire callback in separate thread to not block audio
                        threading.Thread(target=self._fire_wake, daemon=True).start()

        except Exception as e:
            log.error(f"Wake word listener crashed: {e}")

    def _fire_wake(self):
        """Fire the wake callback then reset cooldown."""
        import time
        try:
            self.on_wake()
        except Exception as e:
            log.error(f"Wake callback error: {e}")
        time.sleep(3)  # 3-second cooldown to prevent re-trigger
        self._cooldown = False

    def start(self) -> bool:
        """Start background wake word detection. Returns True if started."""
        if self._running:
            log.warning("Wake word detector already running")
            return True

        if not self._load_model():
            return False

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        log.info("Wake word detector started")
        return True

    def stop(self):
        """Stop the wake word detector."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        log.info("Wake word detector stopped")

    @property
    def is_running(self) -> bool:
        return self._running


# ---------------------------------------------------------------------------
# WebSocket integration helper
# Called from server.py to wire wake word -> JARVIS activation
# ---------------------------------------------------------------------------

_detector: Optional[WakeWordDetector] = None


def start_wake_word_detection(on_wake_callback: Callable[[], None]) -> bool:
    """
    Start the global wake word detector.
    on_wake_callback: function to call when wake word is heard
                      (e.g., send a WebSocket message to activate listening)
    """
    global _detector
    if _detector and _detector.is_running:
        return True

    _detector = WakeWordDetector(on_wake=on_wake_callback)
    return _detector.start()


def stop_wake_word_detection():
    """Stop the global wake word detector."""
    global _detector
    if _detector:
        _detector.stop()
        _detector = None


def is_wake_word_active() -> bool:
    """Check if wake word detection is running."""
    return _detector is not None and _detector.is_running


if __name__ == "__main__":
    import time

    def on_wake():
        print("\n>>> JARVIS ACTIVATED — Wake word detected! <<<\n")

    print(f"Starting wake word detection for: '{WAKE_WORD}'")
    print("Press Ctrl+C to stop.\n")

    if start_wake_word_detection(on_wake):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            stop_wake_word_detection()
    else:
        print("Failed to start. Check logs above.")
