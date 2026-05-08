# UnComicTranslate

English | [한국어](docs/README_ko.md) | [Français](docs/README_fr.md) | [简体中文](docs/README_zh-CN.md) | [日本語](docs/README_ja.md) | [Português Brasileiro](docs/README_pt-BR.md)

## About this Fork

***Made with** ❤️ in Ho Chi Minh City, Vietnam by [Sao Tin Developers](https://github.com/SaoTin) led by [SitriSaleos](https://github.com/SitriSaleos)* 

**UnComicTranslate** is a community-driven fork focused on providing open access to powerful comic translation capabilities using State-of-the-Art (SOTA) Large Language Models.

**Our Mission:**
- **Open Access:** Keep translation capabilities accessible to everyone using their own API keys, without forced credit systems
- **Enhanced Features:** Expand functionality with user flexibility and advanced export options
- **Community-Driven:** Maintain an active development focused on user needs

## Overview

Automatic comic translation tool supporting multiple languages and LLM providers. Translates to and from English, Korean, Japanese, French, Simplified Chinese, Traditional Chinese, Russian, German, Dutch, Spanish, and Italian. Also supports translation to Turkish, Polish, Portuguese, and Brazilian Portuguese.

**Table of Contents:**
- [Installation](#installation)
- [Usage](#usage)
- [API Keys](#api-keys)
- [How It Works](#how-it-works)
- [Features](#features)
- [Acknowledgements](#acknowledgements)

## Installation

### Prerequisites
- Python 3.12
- Git
- uv package manager

### Setup

1. Install Python 3.12 from [python.org](https://www.python.org/downloads/) (check "Add python.exe to PATH")
2. Install Git from [git-scm.com](https://git-scm.com/)
3. Install uv from [docs.astral.sh](https://docs.astral.sh/uv/getting-started/installation/)

4. Clone and setup the repository:
```bash
git clone https://github.com/SitriSaleos/UnComicTranslate
cd UnComicTranslate
uv init --python 3.12
uv add -r requirements.txt --compile-bytecode
```

5. (Optional) For NVIDIA GPU support:
```bash
uv pip install onnxruntime-gpu
```

### Updating

```bash
git pull
uv add -r requirements.txt --compile-bytecode
```

## Usage

Launch the GUI:
```bash
uv run main.py
```

### Tips

- **CBR Files:** If using CBR files, install WinRAR or 7-Zip and add the installation folder to your system PATH. See instructions for [Windows](https://www.windowsdigitals.com/add-folder-to-path-environment-variable-in-windows-11-10/), [Linux](https://linuxize.com/post/how-to-add-directory-to-path-in-linux/), or [Mac](https://techpp.com/2021/09/08/set-path-variable-in-macos-guide/)

- **Font Support:** Ensure your selected font supports characters of the target language

- **Manual Mode:** When automatic mode encounters issues (undetected text, incorrect OCR, insufficient cleaning), use Manual Mode to make corrections. Undo the image and toggle Manual Mode

- **Automatic Processing:** Once an image is processed, it loads in the Viewer while other images continue translating in the background

- **Navigation:** 
  - Ctrl + Mouse Wheel to zoom (or vertical scroll)
  - Trackpad gestures supported
  - Left/Right arrow keys to navigate between images

## API Keys

Configure providers in **Settings -> Credentials -> Select Supplier**.

UnComicTranslate supports over **15+ Providers** (including Online APIs and Local models):

- **OCR:** Runs **locally and is completely free** by default using Manga-OCR, Pororo, or PPOCR. Optional cloud providers (Google/Azure) are available if needed.
- **Translation (LLM):** 
  - **Gemini Flash (2.0/2.5/3):** Highly recommended as Google provides approximately **1,500 free requests per day (RPD)** for these models.
  - **Other providers:** Supports OpenAI (GPT-4o), Anthropic (Claude), Deepseek, Groq, HuggingFace, Ollama (Local), 9Router, and more.

![Credentials Settings](resources/img/Screenshot_Credentials.png)

## How It Works

### Text Detection & Segmentation
Uses RT-DETR-v2 model trained on 11k comic images (manga, webtoons, western comics) for speech bubble and text detection, followed by algorithmic segmentation.

### OCR
**Default providers:**
- [manga-ocr](https://github.com/kha-white/manga-ocr) for Japanese
- [Pororo](https://github.com/yunwoong7/korean_ocr_using_pororo) for Korean
- [PPOCRv5](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html) for other languages

**Optional (requires API key):**
- [Google Cloud Vision](https://cloud.google.com/vision/docs/ocr)
- [Microsoft Azure Vision](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/overview-ocr)

### Inpainting
Removes detected text using:
- Manga/Anime finetuned [lama](https://github.com/advimman/lama) checkpoint
- [AOT-GAN](https://arxiv.org/abs/2104.01431) based model

### Translation
Supports GPT-4o, GPT-4o-mini, DeepL, Claude-3, Gemini-2.5, Yandex, Google Translate, and Microsoft Azure Translator. Full page context provided to LLMs for better translations. Optional image context available.

### Text Rendering
Renders translated text in bounding boxes from detected speech bubbles.

## Features

### Web Export
Export translated projects in web-ready format:
- Clean inpainted images without text
- Structured JSON files with coordinates, original text, and translations
- Perfect for building interactive comic viewers or mobile apps

## Acknowledgements

- [lama-cleaner](https://github.com/Sanster/lama-cleaner)
- [AnimeMangaInpainting](https://huggingface.co/dreMaz/AnimeMangaInpainting)
- [Pororo Korean OCR](https://github.com/yunwoong7/korean_ocr_using_pororo)
- [manga-ocr](https://github.com/kha-white/manga-ocr)
- [EasyOCR](https://github.com/JaidedAI/EasyOCR)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [dayu_widgets](https://github.com/phenom-films/dayu_widgets)
- [Comic-Translate (Original Project)](https://github.com/ogkalu2/comic-translate/)
- [LobeHub (Icon Provider)](https://lobehub.com/)
- [py-googletrans (ssut & community)](https://github.com/ssut/py-googletrans)


