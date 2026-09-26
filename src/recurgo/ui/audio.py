"""Low-latency in-memory stone placement and capture sound effects."""

from __future__ import annotations

import math
import random
import struct
from typing import Protocol

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QTimer
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

from .preferences import AppPreferences


class MoveAudio(Protocol):
    def set_muted(self, muted: bool) -> None: ...

    def play_move(self, *, captured: bool) -> None: ...


class _EffectChannel(QObject):
    def __init__(
        self,
        pcm: bytes,
        audio_format: QAudioFormat,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._pcm = pcm
        self._buffer = QBuffer(self)
        self._sink = QAudioSink(
            QMediaDevices.defaultAudioOutput(),
            audio_format,
            self,
        )
        self._sink.setVolume(0.72)

    def set_pcm(self, pcm: bytes) -> None:
        self._pcm = pcm

    def set_volume(self, volume: float) -> None:
        self._sink.setVolume(max(0.0, min(1.0, volume)))

    def play(self) -> None:
        self._sink.stop()
        self._buffer.close()
        self._buffer.setData(QByteArray(self._pcm))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._sink.start(self._buffer)


class AudioFeedback(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24_000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._available = (
            audio_format.isValid() and not QMediaDevices.defaultAudioOutput().isNull()
        )
        self._muted = False
        self._placement = _EffectChannel(
            _synth_placement_pcm(),
            audio_format,
            self,
        )
        self._capture = _EffectChannel(
            _synth_capture_pcm(),
            audio_format,
            self,
        )

    def configure(self, preferences: AppPreferences) -> None:
        self._placement.set_pcm(_synth_placement_pcm(preferences.placement_sound))
        self._capture.set_pcm(_synth_capture_pcm(preferences.capture_sound))
        volume = preferences.volume / 100.0
        self._placement.set_volume(volume)
        self._capture.set_volume(volume)
        self.set_muted(preferences.muted)

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def play_move(self, *, captured: bool) -> None:
        if self._muted or not self._available:
            return
        self._placement.play()
        if captured:
            QTimer.singleShot(72, self._play_capture)

    def _play_capture(self) -> None:
        if not self._muted and self._available:
            self._capture.play()

    def preview_placement(self) -> None:
        if self._available:
            self._placement.play()

    def preview_capture(self) -> None:
        if self._available:
            self._capture.play()


def _synth_placement_pcm(style: str = "wood") -> bytes:
    sample_rate = 24_000
    duration = {"wood": 0.085, "crisp": 0.060, "soft": 0.115}.get(style, 0.085)
    decay = {"wood": 62.0, "crisp": 86.0, "soft": 43.0}.get(style, 62.0)
    tone_frequency = {"wood": 185.0, "crisp": 330.0, "soft": 145.0}.get(style, 185.0)
    sample_count = round(sample_rate * duration)
    generator = random.Random(19)
    samples: list[float] = []
    previous_noise = 0.0
    for index in range(sample_count):
        time = index / sample_rate
        noise = generator.uniform(-1.0, 1.0)
        softened_noise = noise * 0.65 + previous_noise * 0.35
        previous_noise = noise
        impact = softened_noise * math.exp(-time * decay)
        wooden_body = math.sin(2.0 * math.pi * tone_frequency * time) * math.exp(
            -time * decay * 0.50
        )
        noise_gain = 0.82 if style == "crisp" else 0.58 if style == "soft" else 0.72
        tone_gain = 0.28 if style == "crisp" else 0.38 if style == "soft" else 0.34
        samples.append(impact * noise_gain + wooden_body * tone_gain)
    return _pack_pcm(samples)


def _synth_capture_pcm(style: str = "wood") -> bytes:
    sample_rate = 24_000
    duration = {"wood": 0.19, "crisp": 0.145, "soft": 0.24}.get(style, 0.19)
    sample_count = round(sample_rate * duration)
    generator = random.Random(47)
    impulses = {
        "wood": (0.0, 0.045, 0.092),
        "crisp": (0.0, 0.034, 0.068),
        "soft": (0.0, 0.058, 0.116),
    }.get(style, (0.0, 0.045, 0.092))
    decay = {"wood": 68.0, "crisp": 92.0, "soft": 47.0}.get(style, 68.0)
    base_frequency = {"wood": 310.0, "crisp": 470.0, "soft": 235.0}.get(style, 310.0)
    samples: list[float] = []
    for index in range(sample_count):
        time = index / sample_rate
        value = 0.0
        for impulse_index, start in enumerate(impulses):
            local_time = time - start
            if local_time < 0:
                continue
            envelope = math.exp(-local_time * decay)
            noise = generator.uniform(-1.0, 1.0)
            tone = math.sin(
                2.0 * math.pi * (base_frequency + impulse_index * 75.0) * local_time
            )
            value += (noise * 0.5 + tone * 0.42) * envelope
        gain = 0.55 if style == "soft" else 0.72 if style == "crisp" else 0.68
        samples.append(value * gain)
    return _pack_pcm(samples)


def _pack_pcm(samples: list[float]) -> bytes:
    clipped = [max(-1.0, min(1.0, sample)) for sample in samples]
    return b"".join(struct.pack("<h", round(sample * 30_000)) for sample in clipped)
