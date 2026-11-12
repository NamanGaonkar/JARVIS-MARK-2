# ⚡ JARVIS MARK 2 (JARVIS MARK II)
### The Ultimate Autonomous Multimodal AI Assistant with Movie-Accurate Holographic HUD

<p align="center">
  <img src="hud_preview.png" alt="JARVIS MARK 2 HUD" width="850" />
</p>

> **"Just A Rather Very Intelligent System — Protocol Mark II Online."**
> A real-time voice, vision, and system automation AI built to recreate the iconic Iron Man JARVIS laboratory experience right on your desktop.

---

## 🌟 What is JARVIS MARK 2?

**JARVIS MARK 2** is a personal AI system featuring an **Iron Man movie-accurate amber holographic HUD** and an autonomous digital brain. Powered by bidirectional real-time audio/vision streaming and an extensible multi-provider engine (Google Gemini Live, DeepSeek, Groq, Ollama, LM Studio), JARVIS can hear, speak, see, remember, execute tasks, browse the web, and operate your computer autonomously.

---

## 🎬 Movie-Accurate Holographic HUD

JARVIS MARK 2 features a redesigned visual interface matching Tony Stark's iconic workshop display:

* **3D Celestial Arc Reactor Gyroscope**: A glowing white-hot nuclear core with radiant amber corona and 3-axis gyroscopic orbital rings with segmented holographic tick dashes.
* **Celestial Star Particle Swarm**: Over 450 depth-sorted 3D starlight motes orbiting in perspective space with dynamic shimmer and audio-reactive amplitude swell.
* **Top-Right Digital Chronometer**: Monospaced amber digital clock (`HH:MM:SS`) and date (`DAY DD MON YYYY`) matching the cinematic aesthetic.
* **Tactical GPS / Location HUD Widget**: Amber tactical vector map of **Bengaluru, Karnataka** (HSR Layout) with coordinate crosshairs and live radar ping.
* **Floating Amber System Console**: Real-time terminal log stream floating on the deep-space void (`SYSTEM`, `LINK`, `USER`, `AI`).
* **One-Touch Cinema Mode (`F10`)**: Toggle instantly between full workstation controls and pure, borderless fullscreen Movie HUD.

---

## 🚀 Key Features

| Capability | Description |
|---|---|
| 🎙️ **Real-time Live Voice** | Ultra-low latency voice conversation via Gemini Live / WebSockets with native barge-in and audio interruption. |
| 👁️ **Computer Vision & OCR** | Real-time screen analysis, active window inspection, and camera perception. |
| 🌌 **3D Celestial Core** | Software-rendered 3D gyroscopic particle sphere — zero heavy GPU/OpenGL overhead. |
| 🧠 **Multi-Engine Providers** | Connects to Gemini Live, DeepSeek, Groq, Ollama, OpenAI, Mistral, and local LLMs. |
| 🧵 **Background Autonomous Agents** | Multi-step research and long-running autonomous workflows that run quietly while you continue conversing. |
| 🖥️ **Total Desktop Automation** | Launch apps, control media, manage files, read PDFs/Word/Excel, and control browsers via Playwright. |
| 📱 **Encrypted Remote Dashboard** | Secure HTTPS + AES-256 mobile web dashboard on port `8001` to talk to JARVIS from your phone. |
| 🛡️ **Safety & Confirmation Gate** | Irreversible file operations require spoken or UI confirmation before executing. |
| 🕒 **Routine Engine & Quiet Hours** | Schedule daily briefings, periodic monitors, and quiet hours directly by voice. |

---

## ⌨️ Quick Controls & Shortcuts

| Key | Action |
|---|---|
| <kbd>F10</kbd> | **Toggle Movie HUD Mode** (Hides panels for clean cinematic immersion) |
| <kbd>F11</kbd> | **Toggle Fullscreen** |
| <kbd>F4</kbd> | **Mute / Unmute Microphone** |
| <kbd>Escape</kbd> | **Interrupt JARVIS** (Stops speech immediately) |

---

## 🛠️ Quick Start Guide

### 1. Requirements
* **Python**: 3.11 or 3.12 recommended
* **OS**: Windows 10/11, macOS, or Linux

### 2. Setup

Clone the repository and install dependencies:

```bash
# Clone
git clone https://github.com/FatihMakes/Mark-LVII.git
cd Mark-LVII

# Set up virtual environment and install packages
python -m venv .venv
.venv\Scripts\activate      # On Windows
# source .venv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

### 3. Launching JARVIS MARK 2

On Windows, simply run:
```bat
run_jarvis.bat
```

Or via command line:
```bash
python main.py
```

### 4. API Keys Setup
When launching for the first time, click the **⚙ (Gear)** icon in the header or edit `config/api_keys.json` to insert your Gemini API Key or preferred provider keys:

```json
{
  "assistant_name": "JARVIS",
  "gemini_api_key": "YOUR_GEMINI_API_KEY",
  "ui_color": "#ff9d00",
  "hud_style": "core"
}
```

---

## 🏗️ Architecture

```
VISION (JARVIS MARK 2)
 ├── actions/          # Self-describing modular automation tools & monitors
 ├── agents/           # Markdown-defined autonomous background agent workflows
 ├── config/           # API keys, persistent settings, and application icons
 ├── core/             # Gemini Live client, action loader, TLS, wake word
 ├── dashboard/        # Encrypted mobile web dashboard (FastAPI + HTTPS + AES)
 ├── gui/              # PyQt6 HUD interface
 │    ├── reactor.py   # 3D Celestial Gyroscope & Particle Arc Reactor
 │    ├── hud.py       # Cinematic HUD canvas, clock, log stream, tactical map
 │    ├── window.py    # MainWindow, panels, drawer systems, Movie Mode toggle
 │    └── theme.py     # Palette definition, amber/gold Iron Man styling
 ├── memory/           # Persistent user memory, vector history, config manager
 ├── plugins/          # Extensible plugin system (Tuya, Spotify, WhatsApp, etc.)
 ├── providers/        # Fallback LLM engines (DeepSeek, Groq, Ollama, OpenAI)
 ├── main.py           # Core initialization and background loop orchestration
 └── run_jarvis.bat    # Quick one-click launcher for Windows
```

---

## 📄 License & Attribution

* Original framework and architecture based on **Mark LVII** by [FatihMakes](https://github.com/FatihMakes).
* Customized, upgraded, and themed as **JARVIS MARK 2** featuring the amber cinematic movie HUD.
* Distributed under the MIT License.
