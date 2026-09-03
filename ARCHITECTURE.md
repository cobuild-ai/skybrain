# 🏛️ SkyBrain Architecture Specification

본 문서는 `SkyBrain`의 내부 아키텍처, 설계 원칙, 프로세스 수명주기, 그리고 Metal GPU 최적화 전략을 정의합니다.

---

## 1. 시스템 레이어 구조

```mermaid
graph TD
    subgraph Clients [Clients & Applications]
        A1[DearTalk AI Android/IME]
        A2[Antigravity IDE / Gemini 3.7 Bridge]
        A3[skybrain.journal 인덱서]
        A4[Custom Scripts / Web Services]
        A5[Terminal CLI - skybrain ask]
    end

    subgraph SkyBrain [SkyBrain Serving Daemon]
        API[FastAPI HTTP Router<br>/v1/chat/completions, /v1/models]
        SUP[Supervisor & Process Manager<br>PID/Port/Healthcheck]
        CAT[Model Catalog & Storage<br>~/.skybrain/models]
        ENG[Local Llama.cpp / MLX Engine<br>Metal GPU Acceleration]
        JRN[skybrain.journal Submodule<br>Zero-Loss Indexer & Backup]
    end

    subgraph Gateway [SkyBrain Gateway v2.0]
        GW1[Intent Classifier<br>규칙 기반 + Self-Triage]
        GW2[Conversation History Ring<br>~/.skybrain/history/]
        GW3[Routing Stats Collector<br>~/.skybrain/routing_stats.json]
    end

    A1 -->|OpenAI REST API| API
    A2 -->|OpenAI REST API| API
    A3 -->|Internal Module / API| JRN
    A4 -->|OpenAI REST API| API
    A5 -->|Gateway Classification| GW1

    GW1 --> API
    GW2 -.->|Context Injection| API
    GW3 -.->|Self-Improvement| GW1

    API --> ENG
    SUP --> API
    CAT --> ENG
```

---

## 2. 핵심 컴포넌트

### 1. Model Catalog (`skybrain.engine.model_catalog`)
* **저장소:** `~/.skybrain/models/`
* **지원 프리셋:**
  * `gemma-4-e4b`: `gemma-4-E4B-it-Q4_K_M.gguf` (128k 컨텍스트, Thinking Mode)
  * `gemma-2-2b`: `gemma-2-2b-it.Q4_K_M.gguf` (8k 컨텍스트, 초경량)
  * `qwen-2.5-3b`: Qwen 2.5 3B GGUF
* **기능:** 원자적(Atomic) 다운로드, 상태 파일(`~/.skybrain/state.json`)을 통한 활성 모델 관리.

### 2. OpenAI Compatible Server (`skybrain.server.app`)
* **엔드포인트:**
  * `POST /v1/chat/completions` : 대화형 스트리밍/논스트리밍 추론
  * `GET /v1/models` : 로딩된 모델 및 사용 가능한 모듈 목록 반환
  * `GET /healthz` : 데몬 생존 헬스체크
* **메탈 가속:** `n_gpu_layers=-1`을 통해 모든 레이어를 Apple Silicon Metal GPU에 오프로딩.

### 3. Daemon Supervisor (`skybrain.server.supervisor`)
* 백그라운드 프로세스 실행, PID 추적(`~/.skybrain/skybrain.pid`), 로그 파일(`~/.skybrain/skybrain.log`) 기록 및 정상 종료(Graceful Shutdown) 보장.

### 4. Zero-Config Auto-Provisioning & Client Decoupling
* **무결점 자가 치유(Self-Provisioning):** `DearTalk AI`, `Antigravity IDE` 등 어떤 클라이언트든 사전 수동 설정 없이 데몬이나 스크립트(`scripts/daemon.sh`)를 가동하면 누락된 가중치를 감지하여 안전하게 자동 수급 및 서빙 상태로 진입합니다.
* **클라이언트 비종속(Zero Client Coupling):** 특정 애플리케이션에 종속된 전용 분기를 두지 않고, 오직 표준 OpenAI REST API 규격과 멱등성 런처를 통해 모든 클라이언트에 무결한 서비스를 제공합니다.
* **Auto-Heal via Global CLI:** `shutil.which("skybrain")` 또는 `~/.local/bin/skybrain`을 통해 `uv tool` 표준 경로에서 CLI를 자동 검색하여 데몬을 기동합니다.

### 5. Zero-Loss Journal Submodule (`skybrain.journal`)
* **마크다운 인덱싱 & 백업:** 일자별 개발 일지를 100% 로컬에서 파싱하고, 무손실 `.gz` 백업 및 GitHub 마크다운 대시보드를 생성합니다.

### 6. Gateway v2.0 (`skybrain.gateway`) ⚡ NEW
* **Intent Classifier:** 규칙 기반 + 경량 프롬프트 하이브리드 분류기. 번역, 요약, 로그 분석 등 로컬 처리 가능 작업을 즉시 식별하여 Cloud 토큰 소비 없이 온디바이스 처리.
* **Conversation History Ring:** `~/.skybrain/history/current.jsonl`에 FIFO 방식으로 최근 N턴 대화를 영속 저장. IDE ↔ Terminal 간 Cross-Channel Context Continuity 제공.
* **Routing Stats Collector:** 라우팅 결정(로컬/클라우드), 규칙 적중률, 성공/실패를 추적하여 분류기 자율 개선의 기반 데이터 수집.

---

## 3. 듀얼 모드 아키텍처

### Mode A: Antigravity IDE (오케스트레이션 모드)
Cloud Gemini/Claude가 사령탑으로서 GEMINI.md 규칙 기반으로 SkyBrain에 단순 작업을 위임합니다.
오케스트레이션 토큰이 소모되나, Cloud LLM의 고급 추론 능력을 활용할 수 있습니다.

### Mode B: Terminal (로컬 게이트웨이 모드)
`skybrain ask` CLI가 로컬 Intent Classifier를 통해 즉시 분류하고, 로컬 처리 가능 작업은 Cloud 토큰 0개로 즉시 응답합니다.
대화 히스토리를 통해 IDE 세션의 맥락을 Terminal에서도 참조 가능합니다.

---

## 4. 라이선스
Apache-2.0 License.

