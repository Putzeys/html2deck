# html2deck

Convert any HTML presentation to **PDF**, **PPTX**, and **MP4** — with a live preview interface.

- **PDF/PPTX**: High-res screenshots (3840x2160 @2x) of each slide
- **MP4**: Live browser recording with all CSS animations and transitions
- **Preview UI**: Local web interface to adjust zoom before exporting

## How it works

html2deck uses [Playwright](https://playwright.dev/python/) to render your HTML in a headless browser. It auto-detects slide boundaries using multiple strategies:

| Strategy | When it kicks in |
|---|---|
| **Reveal.js / Remark / Impress / Shower** | Framework detected in the DOM |
| **Keyboard navigation** | Any HTML deck that responds to ArrowRight |
| **Scroll chunking** | Regular HTML pages (no slides) |
| **`--selector`** | Manual CSS selector override |

## Install

```bash
pip install playwright python-pptx Pillow
playwright install chromium
```

## Usage

### CLI

```bash
# PDF + PPTX (default)
python html2deck.py slides.html

# MP4 video with all CSS animations
python html2deck.py slides.html -f mp4

# Everything
python html2deck.py slides.html -f all

# Zoom content 30% bigger
python html2deck.py slides.html --zoom 130

# Custom output path
python html2deck.py slides.html -o ~/Desktop/my-deck

# Force slide selector
python html2deck.py slides.html --selector ".my-slide"

# 5 seconds per slide in video
python html2deck.py slides.html -f mp4 --duration 5
```

### Preview UI

```bash
python server.py slides.html --port 3005
# open http://localhost:3005
```

The preview interface lets you:
- Adjust CSS zoom with a live slider
- Preview at different scales
- Download PDF, PPTX, or MP4 with one click

## Options

| Flag | Default | Description |
|---|---|---|
| `-f, --format` | `both` | `pdf`, `pptx`, `mp4`, `both`, or `all` |
| `-o, --output` | same as input | Output base path (no extension) |
| `--zoom` | `100` | CSS zoom % (130 = 30% bigger content) |
| `--width` | `1920` | Viewport width in px |
| `--height` | `1080` | Viewport height in px |
| `--scale` | `2.0` | Device pixel ratio for screenshots |
| `--wait` | `800` | Wait ms between slide transitions |
| `--duration` | `4.0` | Seconds per slide in MP4 |
| `--selector` | — | Force CSS selector for slide elements |
| `--debug` | — | Save individual slide PNGs |

## Why screenshots?

PPTX slides are images, not native editable elements. Recreating arbitrary HTML as native PowerPoint shapes would require mapping every CSS property to OOXML — feasible for simple layouts, but not generic enough for any HTML.

The tradeoff:
- **Screenshots**: 100% visual fidelity, not editable
- **MP4**: 100% fidelity with animations, not editable
- **Native PPTX**: Would be editable but ~80% fidelity at best

For presentations with CSS animations, **MP4 is the best output** — it captures everything the browser renders.

## License

MIT
