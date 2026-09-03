# 🧠 SkyBrain: Engine AI On-Device Universal & Peninjau Kode 5-Lensa

<div align="center">

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.ko.md">한국어</a> |
  <b>Bahasa Indonesia</b>
</p>

[![Platform: Apple Silicon](https://img.shields.io/badge/Platform-macOS%20Apple%20Silicon%20(Metal)-black?logo=apple&logoColor=white)](#-fitur-utama-platform)
[![Inference: Metal GPU](https://img.shields.io/badge/Inference-Apple%20Metal%20GPU%20(Zero--Docker)-blueviolet)](#-akselerasi-metal-gpu-native-tanpa-docker)
[![API: OpenAI Compatible](https://img.shields.io/badge/API-Kompatibel%20OpenAI%20v1-412991?logo=openai&logoColor=white)](#-rest-api-lokal-kompatibel-openai)
[![Package: uv tool](https://img.shields.io/badge/Package-uv%20tool%20(Rust)-FF4088?logo=python&logoColor=white)](#-panduan-cepat-quick-start)
[![Review: 5--Lens Engine](https://img.shields.io/badge/Code%20Review-Multi--Pass%205--Lensa-success)](#-engine-peninjau-kode-multi-pass-5-lensa)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**SkyBrain** adalah daemon penyedia AI on-device native kelas enterprise tanpa Docker yang dirancang khusus untuk komputer Mac Apple Silicon (M1/M2/M3/M4).

Menyediakan serving model bahasa kecil (SLM seperti Qwen, Gemma, Llama) berlatensi nol dengan akselerasi Apple Metal GPU, proxy perutean lokal dengan circuit breaker otomatis saat terjadi kuota habis (429) atau server sibuk (503), serta **Engine Peninjau Kode Multi-Pass 5-Lensa** canggih yang menghasilkan dashboard HTML interaktif mandiri.

[Fitur Utama](#-fitur-utama-platform) • [Contoh Peninjauan 5-Lensa](#-contoh-peninjauan-5-lensa-dalam-praktik) • [Cara Kerja](#-cara-kerja) • [Arsitektur](ARCHITECTURE.md) • [Panduan Cepat](#-panduan-cepat-quick-start) • [Struktur Repositori](#-struktur-repositori) • [Tata Kelola](GEMINI.md)

</div>

---

## 📊 Status Rilis (Release Status)

| Komponen | Versi | Arsitektur | Status | Sorotan Utama |
| :--- | :---: | :---: | :---: | :--- |
| 🧠 **SkyBrain Core & Daemon** | `v0.2.0` | **macOS Apple Silicon (Metal)** | **Production Stable** | Native Metal GPU tanpa Docker, Supervisor Pemulihan Otomatis 150ms, Pelindung Memori Host (Pre-flight RAM Guard), Circuit Breaker Tanpa Drop |
| 🔍 **Multi-Lens Review Engine** | `v0.2.0` | **5-Lens Strategy Pattern** | **Production Stable** | 5 Lensa (`CleanCode`, `Architecture`, `Security`, `Performance`, `AIConduct`), Verifikasi Fakta Chain-of-Verification, Dashboard HTML Glassmorphism Interaktif |
| 🔌 **SkyBrain MCP Server** | `v0.2.0` | **Model Context Protocol** | **Production Stable** | Integrasi IDE universal (Cursor, VS Code, Antigravity IDE, Claude Desktop) |

---

## 🌟 Fitur Utama Platform

### ⚡ Akselerasi Metal GPU Native Tanpa Docker
- **Kecepatan Native Murni:** Berjalan langsung di macOS tanpa overhead virtualisasi atau beban container Docker.
- **Pemanfaatan Memori Terpadu:** Memanfaatkan arsitektur Unified Memory Apple Silicon 100% tanpa beban penyalinan memori (`-DGGML_METAL=on`).
- **SLM yang Dapat Ditukar Seketika:** Dukungan pergantian mulus antara Qwen 2.5 (3.8B/7B), Google Gemma (2B/4B E4B), dan model GGUF kustom.

### 🌐 REST API Lokal Kompatibel OpenAI
- **Kompatibilitas Penuh:** Menyediakan endpoint `/v1/chat/completions` dan `/v1/models` di `http://127.0.0.1:8000`.
- **Dukungan SDK Universal:** Terintegrasi langsung dengan SDK OpenAI Python/Node, LangChain, LiteLLM, dan LlamaIndex.
- **Pemulihan Mandiri Proxy & SSL Perusahaan:** Mendukung bundel sertifikat inspeksi SSL perusahaan (`SKYBRAIN_CA_BUNDLE`) dan pengecualian lalu lintas lokal (`NO_PROXY`).

### 🛡️ Pelindung Memori Host & Pemulihan Mandiri
- **Pelindung RAM Host (`SystemGuard`):** Terus mengukur RAM yang tersedia menggunakan `sysctl` + `vm_stat` native tanpa latensi. Mencegah macOS macet dengan membatasi inferensi berat jika sisa RAM di bawah 2.5 GB.
- **Pemulihan Otomatis di Bawah 150ms:** Pemeriksaan ping kilat sebelum setiap permintaan; jika daemon berhenti, sistem akan menghidupkannya kembali di latar belakang dalam waktu kurang dari 500ms.
- **Pembersih Proses Atomik:** Menghapus proses yatim dan zombie secara tuntas menggunakan urutan atomik `SIGTERM` ➔ `SIGKILL`.

### 🔍 Engine Peninjau Kode Multi-Pass 5-Lensa
- **Analisis Multi-Perspektif Mandiri:** Memeriksa kode sumber dari 5 disiplin rekayasa perangkat lunak:
  1. 🧹 **Lensa Clean Code:** Prinsip Robert C. Martin, Tanggung Jawab Tunggal (SRP), DRY, penamaan ekspresif.
  2. 🏛️ **Lensa Clean Architecture:** Aturan ketergantungan Uncle Bob (DIP), isolasi batas, pola Contract Facade.
  3. 🛡️ **Lensa Keamanan (Security):** OWASP Top 10, path traversal, celah injeksi, kebocoran exception.
  4. ⚡ **Lensa Kinerja (Performance):** Daur hidup sumber daya (soket/SSL), I/O pemblokir, kompleksitas algoritma.
  5. 🤖 **Lensa AI Conduct (Terbaru):** Mendeteksi anti-pola khas AI: hardcoding data tiruan, halusinasi API fiktif, pembungkaman exception (`except Exception: pass`), dan fungsi TODO yang belum selesai.
- **Chain-of-Verification (CoVe):** Setiap temuan diverifikasi ulang oleh inferensi lokal mandiri untuk menyingkirkan alarm palsu (False Positive).
- **Cache Disk Hash Konten Tier-1:** Memberikan hasil kilat dalam 0.1 detik untuk file yang tidak berubah menggunakan hashing SHA-256.

### 📊 Laporan HTML Interaktif Mandiri
- **Satu File Tanpa Ketergantungan Eksternal:** Laporan HTML lengkap dengan tampilan glassmorphism dark-mode modern yang dapat langsung dibuka di peramban.
- **Penyaringan Interaktif Real-Time:** Saring temuan berdasarkan lensa, tingkat keparahan (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), atau pencarian teks dinamis.
- **Skor Kesehatan Kode (0–100):** Penilaian kesehatan basis kode secara transparan dengan algoritma penalti terbobot.
- **Salin Saran Kode Sekali Klik:** Ekspor saran perbaikan kode langsung ke clipboard dengan satu ketukan.

### 🔀 Proxy Perutean Lokal & Circuit Breaker (Gateway Lokal)
- **Pengalihan Tanpa Putus:** Mengarahkan permintaan ke cloud LLM (Gemini, Claude, OpenAI) dan secara otomatis beralih ke SLM on-device lokal jika kuota habis (HTTP 429) atau server sibuk (HTTP 503).

---

## 🎭 Contoh Peninjauan 5-Lensa dalam Praktik

| Lensa | Anti-Pola yang Terdeteksi | Tingkat Keparahan | Saran Perbaikan AI |
| :--- | :--- | :---: | :--- |
| 🤖 **AI Conduct** | Hardcoding nilai tiruan `return {"status": "ok"}` | 🚨 **CRITICAL** | Terapkan query database dinamis yang sebenarnya atau lempar `NotImplementedError` eksplisit. |
| 🛡️ **Security** | `except Exception: pass` membungkam kegagalan | 🔴 **HIGH** | Tangkap exception spesifik `(json.JSONDecodeError, OSError)` dan catat dengan `logger.warning()`. |
| 🏛️ **Architecture** | Lapisan dalam bergantung langsung pada model konkret (`pelanggaran DIP`) | 🔴 **HIGH** | Terapkan **Pola Contract Facade** di `base.py` dan ekspor kembali tipe abstraksi. |
| ⚡ **Performance** | `ssl.SSLContext` dibuat berulang kali tanpa penggunaan kembali | 🟡 **MEDIUM** | Cache atau bungkus pembuatan konteks dalam fungsi helper dengan manajemen daur hidup. |
| 🧹 **Clean Code** | Angka ajaib `-1` digunakan untuk offload layer GPU | 🟡 **MEDIUM** | Deklarasikan konstanta modul secara eksplisit: `ALL_GPU_LAYERS = -1`. |

---

## 🔄 Cara Kerja

```mermaid
sequenceDiagram
    autonumber
    actor Dev as 👨‍💻 Pengembang / IDE (MCP)
    participant CLI as 🖥️ SkyBrain CLI (`uv tool`)
    participant Guard as 🧠 Pelindung Memori (RAM Guard)
    participant Super as 🩺 Supervisor (Auto-Heal)
    participant Engine as 🔍 Engine Review (5 Lensa)
    participant Daemon as ⚡ Daemon On-Device (Metal SLM)
    participant HTML as 📊 Generator Laporan HTML

    Dev->>CLI: skybrain review ./src --html
    CLI->>Guard: Periksa ketersediaan Unified Memory macOS
    Guard-->>CLI: Memori Aman (Tersedia 6.5 GB)
    CLI->>Super: check_health_fast()
    alt Daemon Mati
        Super->>Super: Hidupkan kembali daemon di latar belakang
    end
    CLI->>Engine: Jalankan Peninjauan Multi-Pass 5-Lensa
    loop Untuk Setiap Lensa (CleanCode, Architecture, Security, Performance, AIConduct)
        Engine->>Daemon: Kirim prompt sistem + potongan kode
        Daemon-->>Engine: Kembalikan temuan JSON terstruktur
        Engine->>Daemon: Chain-of-Verification (Verifikasi fakta temuan)
        Daemon-->>Engine: Temuan yang telah terverifikasi
    end
    Engine->>HTML: Buat laporan HTML interaktif mandiri
    HTML-->>Dev: Tersimpan di ~/.skybrain/reports/review_report_*.html
```

---

## 📦 Panduan Cepat (Quick Start)

### 1. Instalasi CLI Global Sekali Sentuh (`uv tool` - Direkomendasikan)
SkyBrain menerapkan **Standar Universal `uv tool`** untuk lingkungan pengembang yang terisolasi, stabil, dan berkinerja tinggi:

```bash
# Instalasi CLI global (Lingkungan terisolasi dengan akselerasi Metal)
CMAKE_ARGS="-DGGML_METAL=on" uv tool install git+https://github.com/cobuild-ai/skybrain.git

# Atau Instalasi Pengembang Lokal (Mode Editable - perubahan kode langsung aktif)
git clone https://github.com/cobuild-ai/skybrain.git
cd skybrain
CMAKE_ARGS="-DGGML_METAL=on" uv tool install --editable .
```

### 2. Skrip Penyiapan Otomatis Sekali Sentuh (`setup.sh`)
```bash
./setup.sh
```
`setup.sh` akan mendeteksi chip Apple Silicon, mengompilasi binding Metal, menjalankan 111 unit test, mendaftarkan perintah global `skybrain`, dan menghasilkan konfigurasi `.vscode/mcp.json` untuk IDE.

### 3. Perintah CLI Umum
```bash
# Jalankan daemon on-device di latar belakang (Unduh otomatis model jika belum ada)
skybrain start

# Periksa status real-time & pelindung memori host
skybrain status

# Jalankan Peninjauan Kode 5-Lensa pada file atau direktori
skybrain review ./skybrain/core/config.py

# Ajukan pertanyaan ke SLM on-device tanpa biaya token cloud ($0 Token)
skybrain ask "Jelaskan Prinsip Pembalikan Ketergantungan (DIP) dalam Clean Architecture"

# Ajukan pertanyaan dengan eskalasi cloud dan failover circuit breaker lokal
skybrain ask "Buat rencana refactoring arsitektur skala besar" --cloud

# Hentikan daemon latar belakang
skybrain stop
```

---

## 💻 Integrasi Model Context Protocol (MCP)

SkyBrain dilengkapi server Model Context Protocol (MCP) bawaan, menghubungkan SLM Apple Silicon lokal Anda secara instan ke **Cursor, VS Code (Cline / Roo Code), Claude Desktop, dan Antigravity IDE**:

* **Alat MCP yang Tersedia**:
  * `skybrain_expert_consensus`: Jalankan peninjauan kode 5-Lensa langsung di dalam IDE Anda.
  * `skybrain_query`: Ajukan pertanyaan ke Metal SLM lokal tanpa biaya token cloud.
  * `skybrain_translate`: Terjemahan luring instan untuk 12 bahasa.
  * `skybrain_summarize_logs`: Ringkasan cepat log build/runtime berukuran besar secara offline.

---

## 📁 Struktur Repositori

```
skybrain/
├── pyproject.toml              # Konfigurasi standar proyek Python modern (uv & PEP 621)
├── setup.sh                    # Skrip penyiapan otomatis & konfigurasi IDE MCP
├── ARCHITECTURE.md             # Dokumen arsitektur sistem mendalam & diagram circuit breaker
├── GEMINI.md                   # Pedoman tata kelola enterprise & prinsip Truth-First
│
├── skybrain/
│   ├── cli/                    # Perintah CLI berbasis Typer (start, stop, status, review, ask)
│   │   └── main.py
│   ├── core/                   # Pengaturan inti & pelindung perangkat keras
│   │   ├── config.py           # Pydantic BaseSettings, bundel SSL & konfigurasi proxy
│   │   └── monitor.py          # Pemantau memori sysctl/vm_stat native & SystemGuard
│   ├── engine/                 # Engine inferensi SLM Metal Apple Silicon
│   │   └── model_catalog.py    # Binding llama-cpp-python & pengunduh otomatis model GGUF
│   ├── gateway/                # Proxy Perutean Lokal & Circuit Breaker
│   │   └── proxy.py            # Klien failover otomatis cloud-ke-lokal saat HTTP 429/503
│   ├── server/                 # Daemon latar belakang FastAPI & supervisor
│   │   ├── app.py              # Endpoint /v1 standar OpenAI & telemetri memori
│   │   └── supervisor.py       # Pembersih proses atomik & supervisor pemulihan otomatis 150ms
│   ├── review/                 # Platform Peninjau Kode Multi-Pass 5-Lensa
│   │   ├── models.py           # Model domain murni (Severity, Category, Finding, Report)
│   │   ├── engine.py           # Orkestrator multi-pass dengan pelacakan Rich Progress
│   │   ├── verification.py     # Verifikator fakta Chain-of-Verification (CoVe)
│   │   ├── html_report.py      # Generator dashboard HTML glassmorphism interaktif mandiri
│   │   └── lenses/             # Lensa peninjau berbasis Strategy Pattern
│   │       ├── base.py         # Contract Facade yang mengekspor kembali tipe abstraksi
│   │       ├── clean_code.py   # Lensa prinsip Clean Code Robert C. Martin
│   │       ├── clean_architecture.py # Lensa pembalikan ketergantungan & batas lapisan
│   │       ├── security.py     # Lensa keamanan OWASP, path traversal & exception
│   │       ├── performance.py  # Lensa daur hidup sumber daya & efisiensi I/O
│   │       └── ai_conduct.py   # Lensa audit anti-pola AI (hardcoding, halusinasi, stub)
│   └── mcp/                    # Server Model Context Protocol untuk IDE
│
└── tests/                      # 111 rangkaian pengujian pytest (100% lulus)
```

---

## 🔒 Privasi, Prinsip Truth-First & Tata Kelola

1. **Protokol Truth-First (Kebijakan Nol Rekayasa):**
   - Tidak ada balasan tiruan, status palsu, atau trik regex. Semua wawasan berasal dari inferensi SLM lokal yang terverifikasi dan nyata.
2. **100% Privasi On-Device:**
   - Nol telemetri, tanpa perekaman ketikan, dan tanpa ketergantungan cloud untuk operasi lokal. Seluruh kode yang ditinjau tetap berada di dalam memori Mac Apple Silicon Anda.
3. **Mandat Standar Universal `uv tool`:**
   - Tidak ada instalasi `pip` global lawas atau masalah path virtualenv yang rentan rusak. Semua alat CLI dikelola dengan aman melalui lingkungan `uv tool` yang terisolasi dan berkinerja tinggi.

---

## 📄 Lisensi & Pemelihara

- **License:** Apache License 2.0
- **Organization:** [cobuild-ai](https://github.com/cobuild-ai)
- **Maintainer:** `smilelife` (<mysmilelife@gmail.com>)
- **Public Support:** <deartalkai.dev@gmail.com>
