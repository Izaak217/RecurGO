from recurgo.ui.audio import _synth_capture_pcm, _synth_placement_pcm


def test_generated_audio_effects_are_nonempty_16_bit_pcm() -> None:
    placement = _synth_placement_pcm()
    capture = _synth_capture_pcm()

    assert len(placement) > 2_000
    assert len(capture) > len(placement)
    assert len(placement) % 2 == 0
    assert len(capture) % 2 == 0
    assert any(value != 0 for value in placement)
    assert any(value != 0 for value in capture)


def test_builtin_audio_styles_produce_distinct_pcm() -> None:
    placement = {_synth_placement_pcm(style) for style in ("wood", "crisp", "soft")}
    capture = {_synth_capture_pcm(style) for style in ("wood", "crisp", "soft")}

    assert len(placement) == 3
    assert len(capture) == 3
