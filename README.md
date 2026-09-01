# 🧠 SkyBrain: Universal On-Device AI Serving Daemon

> **Docker-Free, Pure Native, OpenAI-Compatible Local SLM/LLM Engine with Apple Silicon Metal GPU Acceleration**

`SkyBrain`은 macOS/Apple Silicon 환경에서 Docker 없이 네이티브 Metal GPU 가속으로 경량 언어 모델(Gemma 4, Gemma 2, Qwen 등)을 단일 상주시키고, **표준 OpenAI REST API 규격(`http://127.0.0.1:8000/v1`)**으로 로컬의 모든 애플리케이션(`DearTalk AI`, `Antigravity IDE`, `skybrain.journal` 등)에 초저지연 AI 서비스를 제공하는 초경량 데몬이자 개발자 도구 패키지입니다.

---

## ✨ 핵심 특징 (Key Features)

* **🚀 Docker-Free & Apple Silicon Native:** 가상화 오버헤드 없이 Mac 통합 메모리(Unified Memory)와 Metal GPU를 100% 활용합니다.
* **🌐 OpenAI API 호환:** `/v1/chat/completions`, `/v1/models` 엔드포인트를 제공하여 기존 모든 LLM SDK(`openai`, `litellm`, `langchain` 등)와 즉시 연동됩니다.
* **🧩 모듈/모델 핫스왑 (Hot-Swappable Models):**
  * `Gemma 4 E4B Instruct` (128k 컨텍스트, Thinking Mode 기본 탑재, 권장)
  * `Gemma 2 2B Instruct` (초경량 베이스라인)
  * `Qwen 2.5 / Phi-4 / Llama 3` 등 필요에 따라 즉시 확장 가능
* **⚡ 제로 컨피그 자동 프로비저닝 (Zero-Config Auto-Provisioning):** 모델이 없어도 번거로운 수동 다운로드 없이, `skybrain start` 또는 `scripts/daemon.sh start`만 실행하면 누락된 가중치(~Gemma 4 E4B)를 스스로 다운로드하고 즉시 서빙합니다.
* **📖 내장 저널 인덱서 (`skybrain.journal`):** 개발 일지 마크다운을 100% 온디바이스로 스캔하여 무손실 `.gz` 백업 및 GitHub 대시보드를 자동 생성합니다.

---

## 📦 빠른 시작 (Zero-Config Quick Start)

### 🚀 초간편 원클릭 실행 (데몬 기동)
사전 설정이나 모델 다운로드에 대한 고민 없이 루트에서 스크립트 하나로 가상환경 구성, 모델 자동 다운로드, 백그라운드 데몬 기동까지 한 번에 완료됩니다.
```bash
# 데몬 시작 (모델 미설치 시 자동 다운로드 후 백그라운드 기동)
./start.sh

# 데몬 중지
./stop.sh
```

---

### 🛠️ CLI 수동 제어
```bash
# 백그라운드 AI 서빙 데몬 시작 (모델 미설치 시 자동 다운로드 후 시작)
skybrain start

# 사용 가능한 모델 목록 확인
skybrain model list

# 모델 전환 (미설치 모델일 경우 자동 다운로드 지원)
skybrain model use gemma-4-e4b

# 데몬 상태 및 헬스체크
skybrain status

# 데몬 중지
skybrain stop
```

---

## 📖 저널 인덱서 서브모듈 (`skybrain.journal`)

```bash
# 일지 인덱싱 및 무손실 .gz 백업 실행
python3 -m skybrain.journal.cli index --source ../../Journal/2026 --output ../../Journal/README.md
```

---

## 🤝 타 프로젝트 연동 가이드

### Python (`DearTalk AI`, `Antigravity IDE` 연동)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="skybrain-local"  # 로컬 인증용 (임의값)
)

response = client.chat.completions.create(
    model="gemma-4-e4b",
    messages=[
        {"role": "system", "content": "당신은 지능형 AI 어시스턴트입니다."},
        {"role": "user", "content": "안녕하세요!"}
    ]
)
print(response.choices[0].message.content)
```

### cURL
```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma-4-e4b",
    "messages": [{"role": "user", "content": "SkyBrain 작동 테스트"}]
  }'
```

---

## 🏛️ 아키텍처 개요
자세한 기술 설계 및 내부 구조는 [`ARCHITECTURE.md`](ARCHITECTURE.md)를 참고하세요.

## 📄 라이선스
Apache-2.0 License.
