# Templates

The **canonical way** to start new content is the scaffolding scripts — they emit
schema-valid, richly-commented starters with sensible defaults already filled in:

```bash
python scripts/new_world.py "My World" --age 5-7
python scripts/new_character.py my-world "Hero Name"
python scripts/new_story.py my-world "Story Title" --age 5-7
```

Each writes a starter you then flesh out (look for `TODO` markers) — with the **JSON-patch edit
scripts**, never by editing the YAML text (they deep-merge a small JSON payload from stdin,
validate the merged document, and write atomically, so a broken file is impossible):

```bash
python scripts/edit_world.py my-world <<'JSON'
{"tagline": "...", "art_style": {"prompt_style_block": "..."}}
JSON
python scripts/edit_character.py my-world/hero-name <<'JSON'
{"appearance_token": "..."}
JSON
python scripts/edit_story.py my-world/story-title pages <<'JSON'
[{"number": 1, "text": "...", "image": {"prompt": "...", "alt": "..."}}]
JSON
```

(`edit_story.py` also has `meta` for top-level fields/spine and `interaction <page>` for games;
pages merge by `number`, JSON `null` deletes a key.) The authoritative shape of
every file is the JSON Schema it must satisfy:

- World → [`schemas/world.schema.json`](../schemas/world.schema.json)
- Character → [`schemas/character.schema.json`](../schemas/character.schema.json)
- Story → [`schemas/story.schema.json`](../schemas/story.schema.json)

For a complete, real-world reference to copy from, read the shipped example under
[`worlds/whispering-woods/`](../worlds/whispering-woods/) — a fully-authored world, two
character bibles (with appearance tokens, palettes, and an evolution track), and a validated
16-page interactive story.

Run `python scripts/validate.py worlds/<slug>` after editing to check your content against the
schemas and the consistency / reading-level / accessibility invariants.
