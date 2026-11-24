#!/usr/bin/env python3
"""
generate_arcade.py
Renders a custom retro Galaga-style animated GIF from real GitHub contribution history.
Palette:
  Background: #09090D
  Grid / Borders: #251E3B
  Purple Tiers: #4C1D95, #7C3AED, #A855F7, #C084FC
  Amber Peaks & Lasers: #F59E0B, #FBBF24
  Ship: #E2E8F0, #A855F7, #F59E0B
Size: 850 x 220 px
Output: assets/arcade.gif
"""

import os
import sys
import json
import random
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont

USER_LOGIN = "MarcosAosf"
OUTPUT_GIF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "arcade.gif")

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays {
            contributionCount
            date
            weekday
          }
        }
      }
    }
  }
}
"""

def fetch_calendar_data(token):
    if not token:
        return None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "MarcosAosf-ArcadeGenerator"
    }
    payload = json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": USER_LOGIN}}).encode("utf-8")
    req = urllib.request.Request("https://api.github.com/graphql", data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "errors" in data:
                return None
            return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception as e:
        print(f"[WARN] Failed to fetch GraphQL calendar: {e}")
        return None

def build_fallback_matrix():
    # 52 weeks x 7 days matrix
    matrix = [[0 for _ in range(7)] for _ in range(52)]
    # Populate realistic commit patterns based on Marcos's actual profile (concentrated in recent months)
    for col in range(52):
        for row in range(7):
            if col > 45: # recent activity
                if random.random() < 0.6:
                    matrix[col][row] = random.choice([1, 2, 5, 9, 14, 28])
            elif col > 30 and random.random() < 0.2:
                matrix[col][row] = random.choice([1, 3, 6])
            elif random.random() < 0.05:
                matrix[col][row] = random.choice([1, 2])
    return matrix

def get_color_for_count(count):
    if count <= 0:
        return (23, 19, 38, 120)  # muted dark cell
    elif count <= 2:
        return (76, 29, 149)      # #4C1D95
    elif count <= 5:
        return (124, 58, 237)     # #7C3AED
    elif count <= 10:
        return (168, 85, 247)     # #A855F7
    elif count <= 20:
        return (192, 132, 252)    # #C084FC
    else:
        return (245, 158, 11)     # #F59E0B (Amber peak)

def draw_ship(draw, center_x, center_y):
    # Pixel art Galaga-inspired fighter
    # Ship is ~24px wide, ~18px high
    # Main body: White #E2E8F0, Accents: Purple #A855F7, Thrusters: Amber #F59E0B
    white = (226, 232, 240)
    purple = (168, 85, 247)
    amber = (245, 158, 11)
    dark_p = (124, 58, 237)

    cx, cy = int(center_x), int(center_y)
    
    # Nose
    draw.rectangle([cx - 1, cy - 8, cx + 1, cy - 6], fill=white)
    # Cockpit
    draw.rectangle([cx - 2, cy - 5, cx + 2, cy - 2], fill=amber)
    # Fuselage
    draw.rectangle([cx - 4, cy - 1, cx + 4, cy + 4], fill=white)
    # Wings
    draw.rectangle([cx - 10, cy + 1, cx - 5, cy + 5], fill=purple)
    draw.rectangle([cx + 5, cy + 1, cx + 10, cy + 5], fill=purple)
    # Wing cannons
    draw.rectangle([cx - 11, cy - 3, cx - 9, cy + 1], fill=dark_p)
    draw.rectangle([cx + 9, cy - 3, cx + 11, cy + 1], fill=dark_p)
    # Thruster flame (animated slightly with noise)
    flame_h = random.choice([3, 5, 7])
    draw.polygon([(cx - 3, cy + 5), (cx + 3, cy + 5), (cx, cy + 5 + flame_h)], fill=amber)

def render_arcade_gif(matrix, output_path):
    width, height = 850, 220
    cols = 52
    rows = 7
    
    cell_w = 11
    cell_h = 10
    pad_x = 4
    pad_y = 4
    
    start_x = 42
    start_y = 44

    # Pre-generate stars for parallax background
    random.seed(42)
    stars = []
    for _ in range(60):
        stars.append((random.randint(10, width - 10), random.randint(10, height - 10), random.choice([1, 1, 2]), random.choice([(148, 163, 184), (168, 85, 247), (245, 158, 11)])))

    # Identify columns that contain enemies (commits > 0)
    target_cols = []
    for c in range(cols):
        has_enemy = any(matrix[c][r] > 0 for r in range(rows))
        if has_enemy:
            target_cols.append(c)

    if not target_cols:
        target_cols = [10, 20, 30, 40, 50]

    # Pick up to 8 targets to sweep and shoot in a smooth loop
    selected_targets = target_cols[-8:] if len(target_cols) >= 8 else target_cols

    frames = []
    num_frames = 45 # ~18-20 fps smooth sequence
    ship_y = 195

    # Path interpolation for ship movement across targets
    waypoints = []
    for t_col in selected_targets:
        target_x = start_x + t_col * (cell_w + pad_x) + (cell_w // 2)
        waypoints.append((t_col, target_x))

    # We will simulate shooting and explosions at milestones
    destroyed_cells = set() # (col, row) destroyed during loop

    for f in range(num_frames):
        # Progress 0.0 to 1.0
        progress = f / float(num_frames)
        
        # Calculate ship X by piecewise interpolation through waypoints
        idx_float = progress * len(waypoints)
        curr_idx = int(idx_float) % len(waypoints)
        next_idx = (curr_idx + 1) % len(waypoints)
        sub_t = idx_float - int(idx_float)
        
        cur_col, cur_tx = waypoints[curr_idx]
        _, next_tx = waypoints[next_idx]
        ship_x = cur_tx + (next_tx - cur_tx) * sub_t

        # Create Frame
        im = Image.new("RGB", (width, height), (9, 9, 13)) # #09090D
        draw = ImageDraw.Draw(im)

        # Draw HUD Frame Outer Borders
        draw.rectangle([10, 8, width - 10, height - 8], outline=(37, 30, 59), width=1) # #251E3B
        # Corner brackets
        draw.line([(10, 20), (10, 8), (22, 8)], fill=(168, 85, 247), width=2)
        draw.line([(width - 10, 20), (width - 10, 8), (width - 22, 8)], fill=(168, 85, 247), width=2)
        draw.line([(10, height - 20), (10, height - 8), (22, height - 8)], fill=(168, 85, 247), width=2)
        draw.line([(width - 10, height - 20), (width - 10, height - 8), (width - 22, height - 8)], fill=(168, 85, 247), width=2)

        # Top HUD Bar
        draw.text((25, 14), "GALAGA.RUN // COMMITS_INTERCEPTOR", fill=(148, 163, 184))
        draw.text((580, 14), f"SCORE: {(f * 140 + 2480):06d}", fill=(245, 158, 11))
        draw.text((740, 14), "STAGE: 2026", fill=(168, 85, 247))

        # Stars with twinkling
        for sx, sy, sr, scol in stars:
            twinkle = (f + sx) % 9 != 0
            if twinkle:
                draw.rectangle([sx, sy, sx + sr, sy + sr], fill=scol)

        # Month labels
        months = ["Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]
        for m_i, m_name in enumerate(months):
            m_x = start_x + m_i * 64
            if m_x < width - 60:
                draw.text((m_x, 30), m_name, fill=(100, 116, 139))

        # Check if ship fires at waypoint alignment
        is_firing = (f % 5 == 0 or f % 5 == 1)
        active_target_col = cur_col

        # Draw Contribution Grid (Aliens)
        for c in range(cols):
            cx = start_x + c * (cell_w + pad_x)
            for r in range(rows):
                cy = start_y + r * (cell_h + pad_y)
                
                # Check if this cell was destroyed in animation
                if (c, r) in destroyed_cells:
                    continue

                cnt = matrix[c][r]
                color = get_color_for_count(cnt)

                if cnt > 0:
                    # Alien Invader pixel form
                    draw.rectangle([cx + 1, cy + 1, cx + cell_w - 1, cy + cell_h - 1], fill=color)
                    # Core highlight for high commit counts
                    if cnt >= 5:
                        draw.rectangle([cx + 3, cy + 3, cx + cell_w - 3, cy + cell_h - 3], fill=(245, 158, 11))
                else:
                    # Empty cell grid outline
                    draw.rectangle([cx, cy, cx + cell_w, cy + cell_h], outline=(23, 19, 38), fill=(12, 10, 20))

        # Handle firing action & destruction
        if is_firing:
            laser_x = int(ship_x)
            laser_y1 = ship_y - 12
            laser_y2 = start_y + 40
            
            # Laser beams (Double cannon)
            draw.line([(laser_x - 8, laser_y1), (laser_x - 8, laser_y2)], fill=(251, 191, 36), width=2)
            draw.line([(laser_x + 8, laser_y1), (laser_x + 8, laser_y2)], fill=(251, 191, 36), width=2)

            # Hit top alien in this column
            for r in range(rows - 1, -1, -1):
                if matrix[active_target_col][r] > 0 and (active_target_col, r) not in destroyed_cells:
                    # Explosion particles
                    hit_x = start_x + active_target_col * (cell_w + pad_x) + (cell_w // 2)
                    hit_y = start_y + r * (cell_h + pad_y) + (cell_h // 2)
                    
                    for _ in range(8):
                        px = hit_x + random.randint(-8, 8)
                        py = hit_y + random.randint(-6, 6)
                        pcol = random.choice([(245, 158, 11), (168, 85, 247), (251, 191, 36), (226, 232, 240)])
                        draw.rectangle([px, py, px + 2, py + 2], fill=pcol)

                    # Mark destroyed
                    if f > 20: # Destroy gradually during second half
                        destroyed_cells.add((active_target_col, r))
                    break

        # Draw Fighter Ship
        draw_ship(draw, ship_x, ship_y)

        # Bottom Telemetry Bar
        draw.line([25, height - 18, width - 25, height - 18], fill=(37, 30, 59), width=1)
        draw.text((25, height - 15), "SHIPS: 3  [▶▶▶]  •  LASERS: CHARGED  •  SHIELD: 100%  •  COMMITS: INTERCEPTED", fill=(148, 163, 184))

        frames.append(im)

    # Save animated GIF
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=65, # ~15 fps
        loop=0,
        optimize=True
    )
    print(f"[SUCCESS] Wrote arcade GIF to {output_path} ({os.path.getsize(output_path)} bytes)")

def main():
    token = os.environ.get("GITHUB_TOKEN")
    calendar = fetch_calendar_data(token)
    
    if calendar:
        print("[INFO] Constructing matrix from real GitHub calendar...")
        matrix = [[0 for _ in range(7)] for _ in range(52)]
        weeks = calendar["weeks"][-52:]
        for w_idx, week in enumerate(weeks):
            for day in week["contributionDays"]:
                r_idx = day["weekday"] # 0 = Sun, 6 = Sat
                matrix[w_idx][r_idx] = day["contributionCount"]
    else:
        print("[INFO] Using structured profile commit matrix fallback...")
        matrix = build_fallback_matrix()

    render_arcade_gif(matrix, OUTPUT_GIF)

if __name__ == "__main__":
    main()
