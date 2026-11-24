#!/usr/bin/env python3
"""
generate_stats.py
Queries GitHub GraphQL API for user telemetry and builds assets/stats-hud.svg
Styled in Cyber-Ops / Tactical HUD Theme (Purple #A855F7 & Amber #F59E0B)
"""

import os
import sys
import json
import urllib.request
import urllib.error

USER_LOGIN = "MarcosAosf"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "stats-hud.svg")

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    following { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""

def fetch_github_data(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "MarcosAosf-StatsGenerator"
    }
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": USER_LOGIN}}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=payload, headers=headers)
    
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        if "errors" in res:
            raise RuntimeError(f"GraphQL Errors: {res['errors']}")
        return res["data"]["user"]

def compute_metrics(user_data):
    cc = user_data["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total_contribs = cal["totalContributions"]
    commit_contribs = cc["totalCommitContributions"]
    pr_count = user_data["pullRequests"]["totalCount"]
    issue_count = user_data["issues"]["totalCount"]
    followers = user_data["followers"]["totalCount"]
    
    repos = user_data["repositories"]["nodes"]
    repo_count = user_data["repositories"]["totalCount"]
    stars = sum(r.get("stargazerCount", 0) for r in repos)

    # Compute streaks
    all_days = []
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            all_days.append((day["date"], day["contributionCount"]))
    
    current_streak = 0
    max_streak = 0
    temp_streak = 0

    # calculate streaks
    for _, count in all_days:
        if count > 0:
            temp_streak += 1
            if temp_streak > max_streak:
                max_streak = temp_streak
        else:
            temp_streak = 0
            
    # current streak from end
    for _, count in reversed(all_days):
        if count > 0:
            current_streak += 1
        elif current_streak > 0:
            break

    # Calculate Level and XP
    # Base formula: XP = commits*10 + prs*25 + issues*15 + stars*50 + total_contribs*5
    xp = (commit_contribs * 10) + (pr_count * 25) + (issue_count * 15) + (stars * 50) + (total_contribs * 5)
    # Level calculated logarithmically / incrementally
    level = max(1, int(1 + (xp / 350)))
    xp_in_level = xp % 350
    xp_needed = 350
    level_progress = min(100, int((xp_in_level / xp_needed) * 100))

    # Calculate top languages
    lang_usage = {}
    for r in repos:
        for edge in r.get("languages", {}).get("edges", []):
            lname = edge["node"]["name"]
            lcolor = edge["node"].get("color") or "#A855F7"
            lsize = edge.get("size", 0)
            if lname not in lang_usage:
                lang_usage[lname] = {"size": 0, "color": lcolor}
            lang_usage[lname]["size"] += lsize

    total_lang_size = sum(item["size"] for item in lang_usage.values()) or 1
    top_langs = sorted(lang_usage.items(), key=lambda x: x[1]["size"], reverse=True)[:5]
    
    formatted_langs = []
    for name, info in top_langs:
        pct = round((info["size"] / total_lang_size) * 100, 1)
        formatted_langs.append({
            "name": name,
            "pct": pct,
            "color": info["color"]
        })

    return {
        "level": level,
        "xp": xp,
        "xp_progress": level_progress,
        "total_contribs": total_contribs,
        "commits": commit_contribs,
        "prs": pr_count,
        "issues": issue_count,
        "stars": stars,
        "repos": repo_count,
        "followers": followers,
        "current_streak": current_streak,
        "max_streak": max(max_streak, current_streak),
        "langs": formatted_langs
    }

def generate_svg(metrics):
    # Prepare languages bar
    lang_bar_segments = []
    lang_legend_items = []
    current_x = 450
    bar_width = 360
    
    for l in metrics["langs"]:
        seg_w = max(4, (l["pct"] / 100.0) * bar_width)
        lang_bar_segments.append(f'<rect x="{current_x}" y="125" width="{seg_w}" height="8" rx="2" fill="{l["color"]}"/>')
        current_x += seg_w
        
    y_leg = 150
    for idx, l in enumerate(metrics["langs"]):
        x_leg = 450 if idx % 2 == 0 else 630
        y_pos = y_leg + (idx // 2) * 22
        lang_legend_items.append(f'''
        <g>
          <circle cx="{x_leg + 6}" cy="{y_pos - 4}" r="4" fill="{l["color"]}"/>
          <text x="{x_leg + 16}" y="{y_pos}" fill="#E2E8F0" font-size="11" class="mono">{l["name"]}</text>
          <text x="{x_leg + 140}" y="{y_pos}" fill="#94A3B8" font-size="10.5" class="mono">{l["pct"]}%</text>
        </g>
        ''')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 320" width="100%" height="320">
  <defs>
    <linearGradient id="hudBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0F0D18"/>
      <stop offset="70%" stop-color="#09090D"/>
      <stop offset="100%" stop-color="#09090D"/>
    </linearGradient>

    <linearGradient id="xpGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#7C3AED"/>
      <stop offset="50%" stop-color="#A855F7"/>
      <stop offset="100%" stop-color="#F59E0B"/>
    </linearGradient>

    <filter id="purpleGlowHud" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <style>
    .mono {{ font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace; }}
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
    @keyframes pulseLiveDot {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}
    .live-indicator {{ animation: pulseLiveDot 2s infinite ease-in-out; }}
  </style>

  <!-- Background Panel -->
  <rect x="0" y="0" width="850" height="320" rx="8" fill="url(#hudBg)" stroke="#251E3B" stroke-width="1.2"/>

  <!-- Tactical Corners -->
  <path d="M 12 32 L 12 12 L 32 12" fill="none" stroke="#A855F7" stroke-width="2" filter="url(#purpleGlowHud)"/>
  <path d="M 838 32 L 838 12 L 818 12" fill="none" stroke="#A855F7" stroke-width="2" filter="url(#purpleGlowHud)"/>
  <path d="M 12 288 L 12 308 L 32 308" fill="none" stroke="#A855F7" stroke-width="2" filter="url(#purpleGlowHud)"/>
  <path d="M 838 288 L 838 308 L 818 308" fill="none" stroke="#A855F7" stroke-width="2" filter="url(#purpleGlowHud)"/>

  <!-- HUD Top Bar -->
  <text x="35" y="36" fill="#94A3B8" font-size="9" letter-spacing="1.5" class="mono">TELEMETRY_ENGINE // REALTIME_STATS</text>
  <circle cx="770" cy="33" r="3.5" fill="#F59E0B" class="live-indicator"/>
  <text x="780" y="36" fill="#FBBF24" font-size="9.5" font-weight="700" letter-spacing="1" class="mono">LIVE SYNC</text>
  <line x1="35" y1="46" x2="815" y2="46" stroke="#251E3B" stroke-width="0.8"/>

  <!-- Left Column: Level, XP Bar & Core Metrics -->
  <g>
    <!-- Level Badge -->
    <rect x="35" y="62" width="70" height="42" rx="4" fill="#171326" stroke="#7C3AED" stroke-width="1.2"/>
    <text x="70" y="80" fill="#94A3B8" font-size="9" font-weight="700" text-anchor="middle" class="mono">LEVEL</text>
    <text x="70" y="98" fill="#FBBF24" font-size="16" font-weight="900" text-anchor="middle" class="mono">LV.{metrics["level"]}</text>

    <!-- XP Bar & Experience info -->
    <text x="120" y="76" fill="#E2E8F0" font-size="11" font-weight="700" class="mono">OPERATIONAL XP</text>
    <text x="380" y="76" fill="#94A3B8" font-size="10.5" text-anchor="end" class="mono">{metrics["xp"]} PTS ({metrics["xp_progress"]}%)</text>
    
    <rect x="120" y="86" width="260" height="10" rx="3" fill="#131020" stroke="#251E3B" stroke-width="0.8"/>
    <rect x="120" y="86" width="{int(2.6 * metrics['xp_progress'])}" height="10" rx="3" fill="url(#xpGrad)"/>

    <!-- Metrics Matrix Grid (2x3) -->
    <!-- Col 1 -->
    <g class="mono">
      <rect x="35" y="125" width="165" height="52" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="48" y="145" fill="#94A3B8" font-size="9.5">CONTRIBUIÇÕES</text>
      <text x="48" y="166" fill="#E2E8F0" font-size="17" font-weight="800">{metrics["total_contribs"]}</text>

      <rect x="35" y="188" width="165" height="52" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="48" y="208" fill="#94A3B8" font-size="9.5">COMMITS (12M)</text>
      <text x="48" y="229" fill="#A855F7" font-size="17" font-weight="800">{metrics["commits"]}</text>

      <rect x="35" y="250" width="165" height="50" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="48" y="270" fill="#94A3B8" font-size="9.5">STARS COLETADAS</text>
      <text x="48" y="291" fill="#FBBF24" font-size="16" font-weight="800">★ {metrics["stars"]}</text>
    </g>

    <!-- Col 2 -->
    <g class="mono">
      <rect x="215" y="125" width="165" height="52" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="228" y="145" fill="#94A3B8" font-size="9.5">PULL REQUESTS</text>
      <text x="228" y="166" fill="#E2E8F0" font-size="17" font-weight="800">{metrics["prs"]}</text>

      <rect x="215" y="188" width="165" height="52" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="228" y="208" fill="#94A3B8" font-size="9.5">STREAK ATUAL</text>
      <text x="228" y="229" fill="#F59E0B" font-size="17" font-weight="800">{metrics["current_streak"]} DIAS</text>

      <rect x="215" y="250" width="165" height="50" rx="4" fill="#0C0A14" stroke="#251E3B" stroke-width="0.8"/>
      <text x="228" y="270" fill="#94A3B8" font-size="9.5">MAIOR STREAK</text>
      <text x="228" y="291" fill="#C084FC" font-size="16" font-weight="800">{metrics["max_streak"]} DIAS</text>
    </g>
  </g>

  <!-- Vertical Divider -->
  <line x1="415" y1="65" x2="415" y2="300" stroke="#251E3B" stroke-width="1" stroke-dasharray="3 4"/>

  <!-- Right Column: Top Languages Matrix -->
  <g class="mono">
    <text x="450" y="78" fill="#A855F7" font-size="12" font-weight="800" letter-spacing="1">TOP TECNOLOGIAS EM DISPATCH</text>
    <text x="450" y="98" fill="#94A3B8" font-size="9.5">Mapeamento em bytes nos repositórios públicos</text>

    <!-- Language Distribution Multi-Segment Bar -->
    <g>
      <rect x="450" y="125" width="360" height="8" rx="2" fill="#171326"/>
      {''.join(lang_bar_segments)}
    </g>

    <!-- Language Legend Items -->
    <g>
      {''.join(lang_legend_items)}
    </g>
  </g>
</svg>"""
    return svg

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[WARN] GITHUB_TOKEN not found in environment. Using fallback demo metrics.")
        metrics = {
            "level": 7,
            "xp": 2480,
            "xp_progress": 72,
            "total_contribs": 96,
            "commits": 88,
            "prs": 0,
            "issues": 1,
            "stars": 4,
            "repos": 16,
            "followers": 9,
            "current_streak": 3,
            "max_streak": 6,
            "langs": [
                {"name": "Python", "pct": 32.4, "color": "#3572A5"},
                {"name": "JavaScript", "pct": 28.6, "color": "#f1e05a"},
                {"name": "HTML/CSS", "pct": 20.8, "color": "#e34c26"},
                {"name": "Shell", "pct": 11.2, "color": "#89e051"},
                {"name": "TypeScript", "pct": 7.0, "color": "#3178c6"}
            ]
        }
    else:
        try:
            print("[INFO] Fetching metrics from GitHub GraphQL API...")
            data = fetch_github_data(token)
            metrics = compute_metrics(data)
            print("[INFO] Successfully calculated metrics.")
        except Exception as e:
            print(f"[ERROR] Failed to fetch GraphQL data: {e}. Falling back to default.")
            metrics = {
                "level": 7,
                "xp": 2480,
                "xp_progress": 72,
                "total_contribs": 96,
                "commits": 88,
                "prs": 0,
                "issues": 1,
                "stars": 4,
                "repos": 16,
                "followers": 9,
                "current_streak": 3,
                "max_streak": 6,
                "langs": [
                    {"name": "Python", "pct": 32.4, "color": "#3572A5"},
                    {"name": "JavaScript", "pct": 28.6, "color": "#f1e05a"},
                    {"name": "HTML/CSS", "pct": 20.8, "color": "#e34c26"},
                    {"name": "Shell", "pct": 11.2, "color": "#89e051"},
                    {"name": "TypeScript", "pct": 7.0, "color": "#3178c6"}
                ]
            }

    svg_content = generate_svg(metrics)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"[SUCCESS] Wrote SVG to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
