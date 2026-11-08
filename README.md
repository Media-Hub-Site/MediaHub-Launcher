# 🎛️ Media Hub — Launcher v1.1.0

Aplicación de escritorio con diversas herramientas para su uso cotidiano, alguna vez necesitaste convertir archivos a otro formato?
MediaHub-Launcher contiene varias aplicaciones a tu disposición con diversos tipos de conversiones multimedia, mejoras de calidad de imagen con modelos de IA y más.

[Descargar última versión](https://github.com/Media-Hub-Site/MediaHub-Launcher/releases/latest)



---

## 🚀 Herramientas Incluidas
### 1. 🎞️ Multimedia Converter
Conversión profesional de archivos multimedia en modo individual o por lotes.
| Módulo | Formatos soportados |
|---|---|
| **Audio** | `mp3`, `wav`, `flac`, `ogg`, `m4a` |
| **Video** | `mp4`, `mkv`, `avi`, `mov`, `webm` + extracción a `mp3` |
| **Imágenes** | `jpg`, `png`, `webp`, `gif`, `bmp`, `tiff` y más |
| **Reescalador** | Redimensión por píxeles o porcentaje |

### 2. 💬 Subtitle Generator (Whisper IA)
Extrae subtítulos precisos (`.srt`) directamente desde cualquier pista de video o audio usando los potentes modelos de OpenAI ejecutados en tu propio equipo.

### 3. © Bulk Watermark Tool
Aplica marcas de agua transparentes sobre imágenes y videos en lote de manera inteligente con escalado adaptativo, asegurando que tu logotipo luzca perfecto independientemente de la resolución original.

### 4. 🔗 Link Converter (Downloader Inteligente)
Descarga video, audio y fotografías desde redes sociales (YouTube, TikTok, Instagram, X) con detección de tipo de contenido automática impulsada por `yt-dlp`.

### 5. 📄 Document Converter
Conversión de PDF a Word, PowerPoint, Excel e imágenes, además del soporte opcional de Word a PDF de alta fidelidad empleando `comtypes`.

### 6. 🤖 Background Eraser (IA)
Eliminación de fondos de fotografías por lote impulsada por Inteligencia Artificial (`rembg` + `u2net`) con salida en canal alfa `.png`.

### 7. ✨ Quality Enhancer — Real-ESRGAN (IA)
Súper Resolución 4x para amplificar fotografías borrosas y limpiar artefactos, impulsada por el avanzado motor binario `Real-ESRGAN`.

### 8. ✂️ Advanced Audio Cut
Corta o recorta archivos de audio visualizando el waveform interactivo, con soporte en vivo para aplicar Fade In y Fade Out.

---

## 🛠️ Requisitos del Sistema

| Requisito | Detalle |
|---|---|
| **Python** | 3.11 o superior |
| **FFmpeg** | Esencial para conversión de audio, video y aceleración por hardware |
| **Microsoft Word** | Solo para conversión Word → PDF (opcional) |
| **Conexión a Internet** | Solo necesaria para Link Converter y descarga inicial de modelos IA |
| **Sistema Operativo** | Windows 10/11 |

---

## 📦 Instalación VSCode

### 1. Clonar el repositorio
```powershell
git clone https://github.com/Alan-Dave/MediaHub_Converter.git
cd MediaHub_Converter
```

### 2. Crear y activar entorno virtual
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias
```powershell
pip install -r requirements.txt
```

### 4. Instalar FFmpeg (Windows)
```powershell
winget install "FFmpeg (Essentials Build)"
```

---

## 🎮 Ejecución

```powershell
python main.py
```

## ⚙️ Compilación Autónoma (GitHub Actions)
El repositorio viene con un script automatizado. Cada vez que hagas `push` de un tag (`v1.x.x`), los servidores de GitHub Actions construirán el instalador del *Media Hub* y lo subirán directamente a la pestaña **Releases**.
