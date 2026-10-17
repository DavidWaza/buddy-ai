# Buddy AI (web)

A voice assistant page with an animated coral buddy. Tap the mic and talk: the
buddy follows your voice, waits until you pause, then answers out loud with a
generic reply. Everything runs in the browser, so
there's no server and no API key.

| Feature                                      | Browser API                | Where it works                              |
| -------------------------------------------- | -------------------------- | ------------------------------------------- |
| Mic level (halos, bubbles, auto end-of-turn) | Web Audio + `getUserMedia` | All modern browsers, on https or localhost  |
| Spoken reply                                 | `speechSynthesis`          | All modern browsers (voices vary by device) |
| Showing and quoting what you said            | `SpeechRecognition`        | Chrome, Edge, Safari                        |

If something is missing or blocked, the page falls back quietly: it simulates
your voice, or shows captions without sound.

- Sign in with any name: that name is what the buddy calls you. It's a dummy login —
  nothing is checked or sent anywhere, and the name is kept in this browser only
  (`localStorage`). `?name=Ada` in the URL just prefills the field.
- The `X` button signs out when nothing is happening, or stops the current turn.
- The model pill (Waza / Waza Pro / Waza Mini) switches the voice, pitch and pace.
- Keyboard: `Space` talks or finishes, `Esc` stops.

## Develop

```sh
npm install
npm run dev          # http://localhost:5173
npm run test:unit    # conversation logic tests
npm run build        # type-check + production build into dist/
```

- `src/session.ts`: the dummy sign-in
- `src/components/LoginScreen.vue`: the sign-in screen

Code lives in `src/buddy/`:

- `voice.ts`: state machine and replies
- `audio.ts`: browser audio
- `renderer.ts`: the canvas buddy

The screen itself is `src/components/BuddyVoice.vue`.

The original Python desktop version is in `desktop/`. It isn't part of the web build.

## Deploy

The build is a static site (`dist/`). The page needs **https** for the
microphone, and every host below provides it.

**Vercel (CLI, no git needed)**

```sh
npx vercel          # first run: log in, accept the detected Vite settings
npx vercel --prod   # publish to your production URL
```

`.vercelignore` keeps the `desktop/` Python app out of the upload.

**Netlify (drag and drop)**: run `npm run build`, then drop the `dist` folder
onto https://app.netlify.com/drop.

**From GitHub (Vercel or Netlify)**: push this folder to a repository and
import it. Build command `npm run build`, output directory `dist`.

Anyone with the link can open the page. Audio stays in each visitor's browser.
Speech recognition in Chrome and Edge is processed by the browser vendor's servers.
