from buddy_ai.voice import Conversation, Mode, count_syllables


def run(conv, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        conv.step(dt)


def test_full_turn_returns_to_idle():
    conv = Conversation("Ada", seed=1, live_audio=False)
    seen = []
    conv.on_mode_changed(seen.append)
    conv.toggle_mic()
    run(conv, 1.0)
    assert conv.mode is Mode.LISTENING
    conv.toggle_mic()
    run(conv, 30)
    assert seen == [Mode.LISTENING, Mode.THINKING, Mode.SPEAKING, Mode.IDLE]
    assert conv.speech is not None and "{name}" not in conv.speech.text


def test_mic_interrupts_speaking_and_cancel_resets():
    conv = Conversation(seed=2, live_audio=False)
    conv.toggle_mic(); conv.toggle_mic()
    run(conv, 2.5)
    assert conv.mode is Mode.SPEAKING
    conv.toggle_mic()
    assert conv.mode is Mode.LISTENING
    conv.cancel()
    assert conv.mode is Mode.IDLE


def test_levels_stay_in_range():
    conv = Conversation(seed=3, live_audio=False)
    conv.toggle_mic()
    for _ in range(600):
        conv.step(1 / 60)
        assert 0.0 <= conv.level <= 1.0


def test_count_syllables():
    assert count_syllables("hi") == 1
    assert count_syllables("favourite,") == 3


def test_reply_matches_how_much_was_said():
    from buddy_ai.voice import LONG_REPLIES, NO_SPEECH_REPLIES, SHORT_REPLIES
    conv = Conversation("Ada", seed=4, live_audio=False)
    for talk, pool in ((0.0, NO_SPEECH_REPLIES), (1.0, SHORT_REPLIES), (5.0, LONG_REPLIES)):
        conv._talk_time = talk
        assert conv._pick_reply() in [r.format(name="Ada") for r in pool]


def test_synthesize_produces_audio():
    from buddy_ai import audio
    utt = audio.synthesize("Hello there.", "Zira", 1)
    assert utt is not None and utt.duration > 0.3 and 0 < utt.envelope.max() <= 1
