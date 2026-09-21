# Buddy AI — voice interface (Python / PySide6)

A voice-assistant screen with an animated coral "buddy" in the middle.
It listens through your microphone and replies out loud using the
operating system's built-in voice. There is no speech recognition yet, so the
reply is a generic one chosen by how much you said (nothing, a little, a lot).
If the mic or text-to-speech is unavailable, it falls back to a simulation.

## Run

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m buddy_ai            # or: -m buddy_ai --name Ada
```

## Using it

| Action                           | Result                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Tap the mic / `Space`            | Start listening: halos and bubbles follow your real voice level                                         |
| Pause for ~1.5 s, or tap the mic | Buddy thinks (dots orbit), then speaks a reply aloud with moving mouth, rings and word-by-word captions |
| Tap the mic while it speaks      | Interrupt and listen again                                                                              |
| `X` / `Esc`                      | Stop the current turn (`X` while idle closes the window)                                                |
| Model pill                       | Pick Waza / Waza Pro / Waza Mini. Each uses a different voice and pace (Zira, David, Hazel on Windows)  |

## Layout

- `buddy_ai/voice.py`: conversation state machine, generic replies, simulators (no Qt)
- `buddy_ai/audio.py`: live mic level (adaptive noise floor) and text-to-speech playback
- `buddy_ai/buddy.py`: the blob, its face, halos, rings and bubbles
- `buddy_ai/controls.py`: painted buttons, mic button, model pill, toast
- `buddy_ai/window.py`: the screen that puts them together and runs the 60 fps loop
- `tests/`: state machine tests (`.venv\Scripts\python -m pytest tests`)

To answer what was actually said, add speech-to-text (for example Whisper) where
listening ends and pass the transcript to a language model in `Conversation._pick_reply`.
