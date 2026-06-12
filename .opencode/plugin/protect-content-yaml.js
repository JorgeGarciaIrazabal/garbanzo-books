/**
 * Hard-enforces the workspace write path for content YAML (see CLAUDE.md):
 * worlds/**\/*.yaml is CREATED by the scaffolders and EDITED via the JSON-patch
 * scripts (edit_world.py / edit_character.py / edit_story.py) — never with the
 * raw write/edit file tools, because hand-managed YAML indentation is how files
 * break. Throwing here blocks the tool call; the error text re-routes the model
 * to the right command, so the rule is enforced, not just instructed.
 */
export const ProtectContentYaml = async () => {
  const FILE_TOOLS = new Set(["write", "edit", "patch", "multiedit"])
  const CONTENT_YAML = /(^|\/)worlds\/.+\.ya?ml$/

  return {
    "tool.execute.before": async (input, output) => {
      if (!FILE_TOOLS.has(input.tool)) return
      const raw = output.args?.filePath ?? output.args?.file_path ?? ""
      const path = String(raw).replace(/\\/g, "/")
      if (CONTENT_YAML.test(path)) {
        throw new Error(
          `BLOCKED: ${path} is content YAML — never write or edit it as text. ` +
          `Use the JSON-patch scripts instead (small JSON on stdin via a bash heredoc): ` +
          `"uv run python scripts/edit_story.py <world>/<story> meta|pages|interaction <N>", ` +
          `"uv run python scripts/edit_world.py <world>", ` +
          `"uv run python scripts/edit_character.py <world>/<char>". ` +
          `To CREATE a new file use the scaffolders (new_world.py / new_character.py / ` +
          `new_story.py --pages N). See FILE SAFETY in your brief.`
        )
      }
    },
  }
}
