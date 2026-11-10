"""
1990s Retro Audio Subsystem with Chiptune Synth Fallback
"""

import os
import array
import random
import math
import pygame


class SoundManager:
    SOUND_FILES = {
        "footstep": "footstep.wav",
        "prompt_open": "prompt_open.wav",
        "door_locked": "door_locked.wav",
        "key_type": "key_type.wav",
        "cancel": "cancel.wav",
        "door_open": "door_open.wav",
        "chest_open": "chest_open.wav",
        "wrong_answer": "wrong_answer.wav",
        "victory": "victory.wav",
    }

    def __init__(self):
        self.sounds = {}
        self.muted = False
        self.enabled = pygame.mixer.get_init() is not None
        if not self.enabled:
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        sounds_dir = os.path.join(base_dir, "sounds")

        for event_name, filename in self.SOUND_FILES.items():
            loaded_sound = self._try_load_file(base_dir, sounds_dir, filename)
            if loaded_sound is None:
                loaded_sound = self._synthesise_90s_fallback(event_name)
            self.sounds[event_name] = loaded_sound

    def _try_load_file(self, base_dir, sounds_dir, filename):
        stem = os.path.splitext(filename)[0]
        candidates = [
            os.path.join(sounds_dir, filename),
            os.path.join(sounds_dir, f"{stem}.ogg"),
            os.path.join(base_dir, filename),
            os.path.join(base_dir, f"{stem}.ogg"),
            filename,
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return pygame.mixer.Sound(path)
                except pygame.error as e:
                    print(f"Warning: Could not load sound '{path}': {e}")
        return None

    def _build_sound_from_notes(self, notes, volume=0.25):
        init_info = pygame.mixer.get_init()
        if not init_info:
            return None
        sample_rate, _, channels = init_info
        buf = array.array("h")
        max_amp = int(32767 * max(0.0, min(1.0, volume)))

        for freq, duration, wave_type in notes:
            num_samples = int(sample_rate * duration)
            for i in range(num_samples):
                t = i / sample_rate
                progress = i / max(1, num_samples)
                env = max(0.0, 1.0 - (progress ** 1.6))

                if freq <= 0:
                    val = 0
                elif wave_type == "square":
                    phase = (t * freq) % 1.0
                    val = max_amp if phase < 0.5 else -max_amp
                elif wave_type == "triangle":
                    phase = (t * freq) % 1.0
                    tri = 4.0 * abs(phase - 0.5) - 1.0
                    val = int(max_amp * tri)
                elif wave_type == "slide_up":
                    inst_freq = freq * (1.0 + 0.8 * progress)
                    phase = (t * inst_freq) % 1.0
                    val = max_amp if phase < 0.5 else -max_amp
                elif wave_type == "noise":
                    val = int(random.uniform(-1.0, 1.0) * max_amp)
                else:
                    val = int(max_amp * math.sin(2.0 * math.pi * freq * t))

                sample = int(val * env)
                buf.append(sample)
                if channels == 2:
                    buf.append(sample)

        try:
            return pygame.mixer.Sound(buffer=buf)
        except Exception:
            return None

    def _synthesise_90s_fallback(self, event_name):
        if event_name == "footstep":
            return self._build_sound_from_notes([(110, 0.035, "noise")], volume=0.08)
        elif event_name == "prompt_open":
            return self._build_sound_from_notes([
                (523.25, 0.055, "square"),
                (659.25, 0.055, "square"),
                (783.99, 0.09, "square"),
            ], volume=0.20)
        elif event_name == "door_locked":
            return self._build_sound_from_notes([
                (130.81, 0.11, "square"),
                (0, 0.03, "square"),
                (110.00, 0.16, "square"),
            ], volume=0.25)
        elif event_name == "key_type":
            return self._build_sound_from_notes([(1200, 0.02, "square")], volume=0.12)
        elif event_name == "cancel":
            return self._build_sound_from_notes([
                (587.33, 0.06, "triangle"),
                (392.00, 0.09, "triangle"),
            ], volume=0.20)
        elif event_name == "door_open":
            return self._build_sound_from_notes([
                (180, 0.06, "noise"),
                (330.0, 0.07, "square"),
                (440.0, 0.07, "square"),
                (659.25, 0.14, "square"),
            ], volume=0.24)
        elif event_name == "chest_open":
            return self._build_sound_from_notes([
                (523.25, 0.08, "square"),
                (659.25, 0.08, "square"),
                (783.99, 0.08, "square"),
                (1046.50, 0.24, "square"),
            ], volume=0.26)
        elif event_name == "wrong_answer":
            return self._build_sound_from_notes([
                (185.00, 0.16, "square"),
                (155.56, 0.16, "square"),
                (123.47, 0.30, "square"),
            ], volume=0.28)
        elif event_name == "victory":
            return self._build_sound_from_notes([
                (523.25, 0.12, "square"),
                (659.25, 0.12, "square"),
                (783.99, 0.12, "square"),
                (1046.50, 0.18, "square"),
                (783.99, 0.10, "square"),
                (1046.50, 0.40, "square"),
            ], volume=0.30)
        return None

    def play(self, event_name):
        if not self.enabled or self.muted:
            return
        snd = self.sounds.get(event_name)
        if snd:
            snd.play()

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted

