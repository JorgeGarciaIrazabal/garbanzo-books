#!/usr/bin/env python3
"""Game Lab — a live playground for designing storybook games.

Edit an `interaction` block as YAML on the left, pick any story page image as the
backdrop, and PLAY the game on the right — the exact same reader runtime the published
site uses, including the arcade games on the real engine. Iterate here, then paste the
block into story.yaml.

The lab is emitted into the STUDIO PREVIEW build only (build_site.py --include-drafts
calls emit()), so it never ships to the public site / GitHub Pages.

Usage:
    uv run python scripts/game_lab.py          # build studio preview + serve the lab
    make game-lab                              # same
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# One ready-to-play template per arcade game (REAL games only — the new-book policy), so
# an author can start from a working payload instead of a blank box. Legacy minigame types
# still render in published books, but get no template here: never start a new one.
TEMPLATES: dict[str, str] = {
    "arcade-catch": """type: arcade-catch
prompt: Catch Pip's sneeze-sparks before they singe the grass!
data:
  player: { emoji: "🪣", label: "rain-bucket" }
  catch: ["✨", "🔥"]
  avoid: [{ emoji: "🐞", label: "ladybug" }]
  goal: 8
  speed: gentle
  how: Drag the bucket — catch every spark!
  avoid_line: Not the ladybug! She's helping!
feedback: { correct: "The meadow is safe! 🐉", try_again: "Quick, under the sparks!" }
""",
    "arcade-flap": """type: arcade-flap
prompt: Fly Pip through the cloud canyon!
data:
  player: "🐉"
  obstacle: "☁️"
  gates: 6
  speed: gentle
feedback: { correct: "What a flyer! 🌟" }
""",
    "arcade-run": """type: arcade-run
prompt: Race home before the storm — grab every star!
data:
  player: "🏃"
  obstacles: ["🪨", "🪵"]
  collect: "⭐"
  finish: "🏰"
  goal: 7
feedback: { correct: "Home safe — and sparkling! 🏰" }
""",
    "arcade-pop": """type: arcade-pop
prompt: Pop the dream-bubbles before they float away!
data:
  pop: ["🫧", "💭"]
  avoid: [{ emoji: "🐝", label: "sleepy bee" }]
  goal: 10
  avoid_line: Shh — don't wake the bee!
feedback: { correct: "Every dream caught! 🌙" }
""",
    "arcade-toss": """type: arcade-toss
prompt: Toss the berries into Mo's basket!
data:
  projectile: "🫐"
  target: { emoji: "🧺", label: "Mo's basket" }
  goal: 4
feedback: { correct: "Basket FULL — Mo is delighted! 🧺" }
""",
    "arcade-steer": """type: arcade-steer
prompt: Swoop through the night and gather the lost stars!
data:
  player: "🦉"
  collect: "⭐"
  avoid: ["☁️", "🌩️"]
  goal: 8
feedback: { correct: "The sky is bright again! 🌌" }
""",
    "arcade-snake": """type: arcade-snake
prompt: Help Nudo the noodle-dragon slurp up every runaway dumpling!
data:
  player: { emoji: "🐉", label: "Nudo the noodle-dragon" }
  body: "🍜"
  food: ["🥟", "🥠"]
  avoid: [{ emoji: "🌶️", label: "the EXTRA-spicy chili" }]
  goal: 8
  speed: gentle
  how: Swipe to slither — every dumpling makes Nudo LONGER!
  avoid_line: Not the chili! Nudo breathes enough fire already!
feedback: { correct: "Nudo is one very long, very happy dragon. 🐉", try_again: "Curl back around!" }
""",
    "arcade-shoot": """type: arcade-shoot
prompt: Bubble-blast the space-jellies tickling the ship!
data:
  player: { emoji: "🚀", label: "the Bathtub Rocket" }
  shot: "🫧"
  targets: ["🪼", "👾"]
  avoid: [{ emoji: "⭐", label: "baby star" }]
  goal: 9
  speed: normal
  how: Drag to steer — the bubbles fire all by themselves!
  avoid_line: Not the baby star — she's napping!
feedback: { correct: "The ship is tickle-free at last! 🚀", try_again: "Line up under a jelly!" }
""",
    "arcade-maze": """type: arcade-maze
prompt: Sneak through the castle cellar to the birthday cake!
data:
  player: { emoji: "🐭", label: "Crumb the mouse" }
  exit: "🎂"
  collect: "🧀"
  size: normal
  how: Swipe to scurry — grab the cheese on the way!
feedback: { correct: "The first slice goes to Crumb! 🎂" }
""",
    "arcade-build": """type: arcade-build
prompt: Stack the giant's breakfast — a pancake tower to the sky!
data:
  blocks: ["🥞", "🧇", "🍓"]
  goal: 7
  speed: gentle
  how: Tap to drop each pancake right on top of the pile!
feedback: { correct: "Breakfast is SKYSCRAPER tall! 🥞", try_again: "Wait for the swing!" }
""",
    "arcade-whack": """type: arcade-whack
prompt: The popcorn is escaping — bop it back into the pot!
data:
  whack: ["🍿"]
  avoid: [{ emoji: "🐥", label: "the kitchen chick" }]
  goal: 10
  speed: normal
  how: Tap each kernel before it ducks away!
  avoid_line: That's the chick — she's just watching!
feedback: { correct: "Movie night is SAVED! 🍿", try_again: "They're quick — keep bopping!" }
""",
    "arcade-bounce": """type: arcade-bounce
prompt: Bounce the meatball — smash the Great Spaghetti Wall!
data:
  player: { emoji: "🍴", label: "the trusty fork" }
  ball: "🧆"
  bricks: ["🍝", "🥖"]
  rows: 2
  speed: normal
  how: Slide the fork — keep the meatball bouncing!
  avoid_line: Boing! The plate bounced it back!
feedback: { correct: "The wall is spaghetti-smithereens! 🍝" }
""",
}

def _page(images: list[str], reader_scripts: list[str], asset_ver: str) -> str:
    manifest = json.dumps(images, ensure_ascii=False)
    templates = json.dumps(TEMPLATES, ensure_ascii=False)
    scripts = "\n".join(
        f'<script src="../assets/{s}?v={asset_ver}"></script>' for s in reader_scripts
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Game Lab — Garbanzo Books studio</title>
<link rel="stylesheet" href="../assets/styles.css?v={asset_ver}">
<style>
  .lab {{ display: grid; grid-template-columns: minmax(340px, 460px) 1fr; gap: 20px;
         max-width: 1500px; margin: 0 auto; padding: 18px; align-items: start; }}
  .lab-panel {{ background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow);
                padding: 16px; }}
  .lab h1 {{ margin: 4px 0 10px; font-size: 1.3rem; }}
  .lab label {{ font-weight: 700; display: block; margin: 10px 0 4px; }}
  .lab select, .lab input[type=text] {{ width: 100%; font: inherit; padding: 8px 10px;
        border-radius: 10px; border: 2px solid var(--accent); background: #fff; }}
  #yaml {{ width: 100%; min-height: 380px; font: 13px/1.5 ui-monospace, monospace;
           border: 2px solid var(--accent); border-radius: 12px; padding: 10px; resize: vertical; }}
  #run {{ margin-top: 12px; width: 100%; font-size: 1.05rem; }}
  #lab-error {{ color: #b3372f; font-weight: 700; white-space: pre-wrap; margin-top: 8px; }}
  /* the playground reader is boxed (never fullscreen-fixed like the real reader) */
  .lab .reader {{ max-width: none; margin: 0; padding: 0; }}
  .lab #stage {{ position: relative !important; inset: auto !important;
                 width: 100% !important; height: auto !important; aspect-ratio: 4/3; }}
  .lab .reader-controls {{ position: static !important; transform: none !important; }}
  @media (max-width: 900px) {{ .lab {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header class="topbar">
  <a class="brand" href="../index.html">Garbanzo<span>Books</span></a>
  <nav><span class="chip">🧪 Game Lab — studio only, never published</span></nav>
</header>
<div class="lab">
  <div class="lab-panel">
    <h1>🧪 Game Lab</h1>
    <p style="margin:0;color:var(--muted)">Design a game, play it instantly. When it feels
    right, paste the YAML into the page's <code>interaction:</code> block.</p>
    <label for="tpl">Start from a template</label>
    <select id="tpl"></select>
    <label for="backdrop">Page art (the game's backdrop)</label>
    <select id="backdrop"></select>
    <input type="text" id="backdrop-url" placeholder="…or paste any image URL" style="margin-top:6px">
    <label for="yaml">interaction (YAML)</label>
    <textarea id="yaml" spellcheck="false"></textarea>
    <button class="btn" id="run">▶ Run the game</button>
    <div id="lab-error"></div>
  </div>
  <div class="lab-panel">
    <div class="reader">
      <div id="stage"></div>
      <div id="interaction"></div>
      <div class="reader-controls">
        <button class="btn secondary" id="prev" type="button">‹ Back</button>
        <span class="progress pageno" id="pageno"></span>
        <button class="btn" id="next" type="button">Next ›</button>
      </div>
    </div>
  </div>
</div>
<script id="story-data" type="application/json">{{"title":"Game Lab","pages":[]}}</script>
<script src="../assets/vendor/js-yaml.min.js"></script>
{scripts}
<script>
(() => {{
  const TEMPLATES = {templates};
  const IMAGES = {manifest};
  const $ = (id) => document.getElementById(id);

  const tpl = $("tpl");
  Object.keys(TEMPLATES).forEach((name) => tpl.appendChild(new Option(name, name)));
  const backdrop = $("backdrop");
  backdrop.appendChild(new Option("(no art — plain board)", ""));
  IMAGES.forEach((p) => backdrop.appendChild(new Option(p.replace("story/", ""), "../" + p)));
  if (IMAGES.length) backdrop.selectedIndex = 1;

  $("yaml").value = TEMPLATES[tpl.value];
  tpl.onchange = () => {{ $("yaml").value = TEMPLATES[tpl.value]; run(); }};
  backdrop.onchange = () => {{ $("backdrop-url").value = ""; run(); }};
  $("backdrop-url").onchange = run;

  function run() {{
    $("lab-error").textContent = "";
    let it;
    try {{
      it = jsyaml.load($("yaml").value);
      if (!it || typeof it !== "object" || !it.type) throw new Error("the YAML must have a `type:`");
    }} catch (e) {{
      $("lab-error").textContent = "YAML problem: " + e.message;
      return;
    }}
    const img = $("backdrop-url").value.trim() || backdrop.value;
    const story = {{
      title: "Game Lab",
      slug: "game-lab-" + Date.now(),   // fresh slug → fresh sticker state per run
      pages: [{{
        number: 1, kind: "story", text: "",
        image: {{ file: img, alt: "playground backdrop" }},
        interaction: it,
      }}],
    }};
    if (window.GB && GB.teardown) GB.teardown();   // close any fullscreen game
    $("interaction") && ($("interaction").innerHTML = "");
    document.getElementById("story-data").textContent = JSON.stringify(story);
    GB.boot();
    const play = document.querySelector(".play-game-btn");
    if (play) play.click();                         // open the game sheet immediately
  }}
  $("run").onclick = run;
  run();
}})();
</script>
</body>
</html>"""


def emit(site_dir: Path, images: list[str]) -> None:
    """Write the Game Lab page into <site>/game-lab/. Called by build_site.py for
    studio-preview builds only (--include-drafts) — the lab never goes public."""
    from build_site import ASSET_VER, READER_SCRIPTS  # late import: avoid a cycle at module load

    out = site_dir / "game-lab"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(_page(sorted(images), READER_SCRIPTS, ASSET_VER), encoding="utf-8")


def main() -> int:
    from build_site import build

    stats = build(include_drafts=True)
    print(f"+ built studio preview ({stats['stories']} stories) with the Game Lab")
    print("  open: http://localhost:8008/game-lab/")
    import http.server
    import functools
    import socketserver

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory="site")
    with socketserver.TCPServer(("", 8008), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
