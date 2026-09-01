# SkyBrain 불변의 철칙 (Core Principles)

## 🚨 제1철칙: 꼼수는 절대 금지한다 (Zero Fake Rules)
1. **하드코딩 흉내 내기 영구 금지:**
   - 인공지능/추론 엔진을 흉내 내려는 if/else, 문자열 하드코딩 Mock, 빈 stub을 코드베이스에 작성하지 않는다.
   - 실제 Apple Silicon Metal 가속 및 온디바이스 GGUF 엔진(llama.cpp)을 통해 무결한 추론을 수행한다.
2. **독립 마이크로서비스 무결성:**
   - 특정 클라이언트(Continuum, DearTalk 등)에 종속되지 않고, 표준 OpenAI REST API 규격(`http://127.0.0.1:8000/v1`)을 완벽하게 준수한다.
3. **무결성 게이트키퍼 & TDD:**
   - 모든 수정 사항은 단위 테스트 및 API 테스트를 100% 통과해야 한다.
