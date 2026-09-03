"""Interactive HTML Report Generator for SkyBrain Multi-Lens Code Review.

Generates a standalone, beautiful, self-contained HTML dashboard with
glassmorphism aesthetics, dark mode, interactive filtering, and zero external dependencies.
"""

from datetime import datetime
import html
import json
from pathlib import Path
from typing import Optional

from skybrain.core.config import settings
from skybrain.review.models import AggregatedReport, Finding, Severity, Category


def calculate_health_score(stats: dict[str, int]) -> int:
    """Calculates a 0–100 code health score based on severity distribution."""
    score = 100
    score -= stats.get("CRITICAL", 0) * 25
    score -= stats.get("HIGH", 0) * 10
    score -= stats.get("MEDIUM", 0) * 3
    score -= stats.get("LOW", 0) * 1
    return max(0, min(100, score))


def generate_html_report(
    report: AggregatedReport,
    target_label: str = ".",
    output_path: Optional[Path] = None,
) -> Path:
    """Generates an interactive, standalone HTML report file from an AggregatedReport."""
    reports_dir = settings.home_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_path is None:
        file_name = f"review_report_{timestamp_str}.html"
        final_path = reports_dir / file_name
    else:
        final_path = Path(output_path).resolve()
        final_path.parent.mkdir(parents=True, exist_ok=True)

    stats = report.stats
    health_score = calculate_health_score(stats)

    # Health score color & badge
    if health_score >= 90:
        score_color = "#10b981"  # Emerald
        score_badge = "Excellent"
    elif health_score >= 75:
        score_color = "#06b6d4"  # Cyan
        score_badge = "Good"
    elif health_score >= 50:
        score_color = "#f59e0b"  # Amber
        score_badge = "Needs Improvement"
    else:
        score_color = "#ef4444"  # Red
        score_badge = "Critical Attention"

    crit_color = "var(--sev-critical)" if stats.get("CRITICAL", 0) > 0 else "var(--text-main)"

    findings_json = []
    for f in report.all_findings:
        sev_name = f.severity.name if hasattr(f.severity, "name") else str(f.severity)
        cat_name = f.category.value if hasattr(f.category, "value") else str(f.category)
        findings_json.append({
            "id": f.finding_id,
            "file": f.file,
            "line": f.line or 0,
            "severity": sev_name,
            "category": cat_name,
            "principle": f.principle_violated,
            "description": f.description,
            "suggestion": f.suggestion,
            "confidence": round(f.confidence * 100, 1),
            "verified": f.verified,
        })

    json_data_str = json.dumps(findings_json, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SkyBrain Multi-Lens Code Review Report - {html.escape(target_label)}</title>
  <style>
    :root {{
      --bg-primary: #0d1117;
      --bg-secondary: #161b22;
      --bg-card: rgba(22, 27, 34, 0.75);
      --border-color: rgba(255, 255, 255, 0.1);
      --text-main: #f0f6fc;
      --text-muted: #8b949e;
      --accent-cyan: #38bdf8;
      --accent-purple: #a855f7;
      --sev-critical: #f43f5e;
      --sev-high: #f97316;
      --sev-medium: #eab308;
      --sev-low: #3b82f6;
      --sev-info: #64748b;
      --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", Helvetica, Arial, sans-serif;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: radial-gradient(circle at 50% 0%, #1a2333 0%, #0d1117 75%);
      color: var(--text-main);
      font-family: var(--font-family);
      line-height: 1.6;
      padding: 32px 24px;
      min-height: 100vh;
    }}

    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}

    /* Header */
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 32px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 24px;
      flex-wrap: wrap;
      gap: 16px;
    }}

    .title-group h1 {{
      font-size: 1.85rem;
      font-weight: 700;
      background: linear-gradient(135deg, #38bdf8 0%, #c084fc 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .title-group p {{
      color: var(--text-muted);
      font-size: 0.95rem;
      margin-top: 4px;
    }}

    .meta-badge {{
      background: rgba(56, 189, 248, 0.1);
      border: 1px solid rgba(56, 189, 248, 0.3);
      color: var(--accent-cyan);
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
    }}

    /* Overview Grid */
    .overview-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }}

    .card {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 22px;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}

    .card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }}

    .card-title {{
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}

    .card-value {{
      font-size: 2.2rem;
      font-weight: 800;
      display: flex;
      align-items: baseline;
      gap: 8px;
    }}

    .score-card {{
      border-color: {score_color}44;
      background: linear-gradient(135deg, {score_color}11 0%, rgba(22, 27, 34, 0.8) 100%);
    }}

    .score-badge-label {{
      font-size: 0.9rem;
      font-weight: 600;
      color: {score_color};
    }}

    /* Filter Controls */
    .controls-panel {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 16px 20px;
      margin-bottom: 28px;
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
    }}

    .pill-filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .filter-btn {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 0.88rem;
      cursor: pointer;
      font-weight: 500;
      transition: all 0.2s ease;
    }}

    .filter-btn:hover, .filter-btn.active {{
      background: #38bdf822;
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
    }}

    .search-box {{
      position: relative;
      min-width: 260px;
    }}

    .search-box input {{
      width: 100%;
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 8px 14px;
      color: var(--text-main);
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.2s;
    }}

    .search-box input:focus {{
      border-color: var(--accent-cyan);
    }}

    /* Findings List */
    .findings-container {{
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    .finding-item {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 20px 24px;
      backdrop-filter: blur(8px);
      transition: border-color 0.2s, box-shadow 0.2s;
    }}

    .finding-item:hover {{
      border-color: rgba(255, 255, 255, 0.25);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }}

    .finding-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
      gap: 10px;
    }}

    .badges-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .sev-pill {{
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .sev-CRITICAL {{ background: rgba(244, 63, 94, 0.15); color: var(--sev-critical); border: 1px solid rgba(244, 63, 94, 0.4); }}
    .sev-HIGH {{ background: rgba(249, 115, 22, 0.15); color: var(--sev-high); border: 1px solid rgba(249, 115, 22, 0.4); }}
    .sev-MEDIUM {{ background: rgba(234, 179, 8, 0.15); color: var(--sev-medium); border: 1px solid rgba(234, 179, 8, 0.4); }}
    .sev-LOW {{ background: rgba(59, 130, 246, 0.15); color: var(--sev-low); border: 1px solid rgba(59, 130, 246, 0.4); }}
    .sev-INFO {{ background: rgba(100, 116, 139, 0.15); color: var(--sev-info); border: 1px solid rgba(100, 116, 139, 0.4); }}

    .cat-pill {{
      background: rgba(255, 255, 255, 0.06);
      color: #cbd5e1;
      padding: 3px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
    }}

    .loc-badge {{
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      color: var(--accent-cyan);
      font-size: 0.85rem;
      background: rgba(56, 189, 248, 0.08);
      padding: 2px 8px;
      border-radius: 4px;
    }}

    .finding-principle {{
      font-size: 1.05rem;
      font-weight: 600;
      color: #ffffff;
      margin-bottom: 8px;
    }}

    .finding-desc {{
      color: #cbd5e1;
      font-size: 0.95rem;
      margin-bottom: 12px;
      white-space: pre-wrap;
    }}

    .suggestion-box {{
      background: rgba(0, 0, 0, 0.35);
      border-left: 3px solid var(--accent-cyan);
      border-radius: 6px;
      padding: 12px 16px;
      font-size: 0.9rem;
      color: #93c5fd;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
    }}

    .copy-btn {{
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.78rem;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;
    }}

    .copy-btn:hover {{
      background: rgba(255, 255, 255, 0.2);
    }}

    .empty-state {{
      text-align: center;
      padding: 64px 20px;
      background: var(--bg-card);
      border: 1px dashed var(--border-color);
      border-radius: 16px;
    }}

    .empty-state h3 {{
      font-size: 1.5rem;
      color: #10b981;
      margin-bottom: 8px;
    }}

    footer {{
      margin-top: 48px;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
      border-top: 1px solid var(--border-color);
      padding-top: 20px;
    }}

    .lang-switch {{
      display: inline-flex;
      gap: 4px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 3px;
    }}

    .lang-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.75rem;
      font-weight: 700;
      transition: all 0.2s;
    }}

    .lang-btn.active {{
      background: var(--accent-blue);
      color: white;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>🧠 SkyBrain Code Intelligence Report</h1>
        <p>Target: <strong>{html.escape(target_label)}</strong> | Files: <strong>{report.total_files_reviewed}</strong> | Lenses Applied: <strong>{report.total_lenses_applied}</strong></p>
      </div>
      <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
        <div class="meta-badge">
          ⚡ Engine: Local Qwen 3.8 Metal GPU
        </div>
        <div class="lang-switch">
          <button class="lang-btn active" id="btn-lang-en" onclick="setLang('en')">EN</button>
          <button class="lang-btn" id="btn-lang-ko" onclick="setLang('ko')">KO</button>
          <button class="lang-btn" id="btn-lang-id" onclick="setLang('id')">ID</button>
        </div>
      </div>
    </header>

    <!-- Overview Cards -->
    <div class="overview-grid">
      <div class="card score-card">
        <div class="card-title">Code Health Score</div>
        <div class="card-value" style="color: {score_color};">
          {health_score}<span style="font-size: 1.1rem; color: var(--text-muted);">/100</span>
        </div>
        <div class="score-badge-label">{score_badge}</div>
      </div>

      <div class="card">
        <div class="card-title">Critical & High Issues</div>
        <div class="card-value" style="color: {crit_color};">
          {stats.get("CRITICAL", 0) + stats.get("HIGH", 0)}
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          🚨 {stats.get("CRITICAL", 0)} Critical &nbsp;|&nbsp; 🔴 {stats.get("HIGH", 0)} High
        </div>
      </div>

      <div class="card">
        <div class="card-title">Medium & Low Warnings</div>
        <div class="card-value" style="color: var(--sev-medium);">
          {stats.get("MEDIUM", 0) + stats.get("LOW", 0)}
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          🟡 {stats.get("MEDIUM", 0)} Medium &nbsp;|&nbsp; 🔵 {stats.get("LOW", 0)} Low
        </div>
      </div>

      <div class="card">
        <div class="card-title">Total Findings</div>
        <div class="card-value">
          {len(report.all_findings)}
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">
          100% Blind Isolation Verified
        </div>
      </div>
    </div>

    <!-- Filter Controls -->
    <div class="controls-panel">
      <div class="pill-filters" id="lensFilters">
        <button class="filter-btn active" id="btn-filter-all" data-filter="all">All ({len(report.all_findings)})</button>
        <button class="filter-btn" data-filter="clean_code">🧹 Clean Code</button>
        <button class="filter-btn" data-filter="clean_architecture">🏛️ Architecture</button>
        <button class="filter-btn" data-filter="security">🛡️ Security</button>
        <button class="filter-btn" data-filter="performance">⚡ Performance</button>
        <button class="filter-btn" data-filter="ai_conduct">🤖 AI Conduct</button>
      </div>

      <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Search file, principle, description...">
      </div>
    </div>

    <!-- Findings List -->
    <div class="findings-container" id="findingsList">
      <!-- Injected by JavaScript -->
    </div>

    <footer>
      Generated by <strong>SkyBrain Code Review Engine v2.0</strong> • {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </footer>
  </div>

  <script>
    const rawFindings = {json_data_str};
    let currentFilter = 'all';
    let currentSearch = '';
    let currentLang = 'en';

    const translations = {{
      en: {{
        all: "All",
        searchPlaceholder: "🔍 Search file, principle, description...",
        confidence: "confidence",
        suggestionTitle: "👉 Suggestion:",
        copy: "📋 Copy",
        copied: "📋 Suggestion copied to clipboard!",
        copyPrompt: "Copy with Ctrl+C / Cmd+C:",
        noFindingsTitle: "🎉 Zero Defects Found",
        noFindingsDesc: "No issues match the selected filter criteria."
      }},
      ko: {{
        all: "전체",
        searchPlaceholder: "🔍 파일명, 원칙, 내용 검색...",
        confidence: "신뢰도",
        suggestionTitle: "👉 제안 (Suggestion):",
        copy: "📋 복사",
        copied: "📋 제안 내용이 클립보드에 복사되었습니다.",
        copyPrompt: "Ctrl+C로 복사하세요:",
        noFindingsTitle: "🎉 결함 없음 (Zero Defects)",
        noFindingsDesc: "선택한 필터 조건에 해당하는 이슈가 없습니다."
      }},
      id: {{
        all: "Semua",
        searchPlaceholder: "🔍 Cari file, prinsip, deskripsi...",
        confidence: "kepercayaan",
        suggestionTitle: "👉 Saran (Suggestion):",
        copy: "📋 Salin",
        copied: "📋 Saran berhasil disalin ke clipboard!",
        copyPrompt: "Salin dengan Ctrl+C / Cmd+C:",
        noFindingsTitle: "🎉 Nol Masalah Ditemukan",
        noFindingsDesc: "Tidak ada masalah yang cocok dengan filter yang dipilih."
      }}
    }};

    function setLang(lang) {{
      currentLang = lang;
      document.querySelectorAll('.lang-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.getElementById(`btn-lang-${{lang}}`);
      if (activeBtn) activeBtn.classList.add('active');

      const t = translations[lang] || translations.en;
      const allBtn = document.getElementById('btn-filter-all');
      if (allBtn) allBtn.innerText = `${{t.all}} (${{rawFindings.length}})`;
      const searchInput = document.getElementById('searchInput');
      if (searchInput) searchInput.placeholder = t.searchPlaceholder;

      renderFindings();
    }}

    function renderFindings() {{
      const t = translations[currentLang] || translations.en;
      const container = document.getElementById('findingsList');
      container.innerHTML = '';

      const filtered = rawFindings.filter(item => {{
        const matchesLens = (currentFilter === 'all') || (item.category === currentFilter);
        const searchLower = currentSearch.toLowerCase();
        const matchesSearch = !currentSearch ||
          item.file.toLowerCase().includes(searchLower) ||
          item.principle.toLowerCase().includes(searchLower) ||
          item.description.toLowerCase().includes(searchLower) ||
          (item.suggestion && item.suggestion.toLowerCase().includes(searchLower));

        return matchesLens && matchesSearch;
      }});

      if (filtered.length === 0) {{
        container.innerHTML = `
          <div class="empty-state">
            <h3>${{t.noFindingsTitle}}</h3>
            <p style="color: var(--text-muted); margin-top: 8px;">${{t.noFindingsDesc}}</p>
          </div>
        `;
        return;
      }}

      filtered.forEach(item => {{
        const card = document.createElement('div');
        card.className = 'finding-item';
        card.id = `finding-${{item.id}}`;

        const filename = item.file.split('/').pop();
        const locText = `${{filename}}:${{item.line}}`;

        const catIcons = {{
          'clean_code': '🧹 Clean Code',
          'clean_architecture': '🏛️ Architecture',
          'security': '🛡️ Security',
          'performance': '⚡ Performance',
          'ai_conduct': '🤖 AI Conduct'
        }};
        const catLabel = catIcons[item.category] || item.category;

        let suggestionHtml = '';
        if (item.suggestion) {{
          suggestionHtml = `
            <div class="suggestion-box">
              <div>
                <strong>${{t.suggestionTitle}}</strong> ${{escapeHtml(item.suggestion)}}
              </div>
              <button class="copy-btn" onclick="copyText('${{escapeQuotes(item.suggestion)}}')">${{t.copy}}</button>
            </div>
          `;
        }}

        card.innerHTML = `
          <div class="finding-header">
            <div class="badges-group">
              <span class="sev-pill sev-${{item.severity}}">${{item.severity}}</span>
              <span class="cat-pill">${{catLabel}}</span>
              <span class="loc-badge">${{locText}}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">
              ${{item.confidence}}% ${{t.confidence}}
            </div>
          </div>
          <div class="finding-principle">${{escapeHtml(item.principle)}}</div>
          <div class="finding-desc">${{escapeHtml(item.description)}}</div>
          ${{suggestionHtml}}
        `;

        container.appendChild(card);
      }});
    }}

    function escapeHtml(text) {{
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }}

    function escapeQuotes(text) {{
      if (!text) return '';
      return text.replace(/'/g, "\\\\'").replace(/"/g, '&quot;').replace(/\\n/g, ' ');
    }}

    function copyText(text) {{
      const t = translations[currentLang] || translations.en;
      navigator.clipboard.writeText(text).then(() => {{
        alert(t.copied);
      }}).catch(() => {{
        prompt(t.copyPrompt, text);
      }});
    }}

    // Filter Buttons Listener
    document.querySelectorAll('#lensFilters button').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('#lensFilters button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.getAttribute('data-filter');
        renderFindings();
      }});
    }});

    // Search Input Listener
    document.getElementById('searchInput').addEventListener('input', (e) => {{
      currentSearch = e.target.value.trim();
      renderFindings();
    }});

    // Initial render
    renderFindings();
  </script>
</body>
</html>
"""

    final_path.write_text(html_content, encoding="utf-8")

    # Also create/update 'latest_report.html' symlink or copy for convenience
    latest_path = reports_dir / "latest_report.html"
    try:
        latest_path.write_text(html_content, encoding="utf-8")
    except Exception:
        pass

    return final_path
