# picogame documentation sources

This is the prose behind <https://picogame.makerclass.cz>. It lives here, in the public repo, so
that **anyone can send a pull request** — a typo, a clearer sentence, a missing warning, a
translation. The site is generated from these files; there is no other copy to keep in sync.

## What is where

| Path | What it is |
|---|---|
| `*.md` | one page each, English (`REFERENCE.md` → `/reference/`, `HARDWARE.md` → `/hardware/`, …) |
| `cs/<slug>.md` | the Czech translation of that page (`cs/reference.md`). Missing ones fall back to English |
| `pages/**.md` | pages written directly for the site (concepts, helpers, quickstart); they already carry Starlight frontmatter |
| `pages/cs/**.md` | their Czech counterparts |
| `img/`, `audio/` | published assets; reference them as `img/name.png` (from `cs/`, `../img/name.png`) |

Pages that embed live components — the playground, the scene editor, the tutorials walkthroughs —
are `.mdx` and stay with the site code, not here. They are page *architecture* rather than prose.

## Sending a change

Edit the `.md` and open a PR. Useful to know:

- **English and Czech are separate files.** A factual fix (a number, a flag name, a corrected
  claim) should change **both**, or the Czech page keeps stating the old fact. Pure wording
  improvements in one language are fine on their own.
- **Keep the heading structure of a page and its translation the same.** The build checks the
  sequence of heading levels between each EN/CZ pair and fails on a mismatch — sections are how
  cross-language links stay valid.
- **The first `# H1` becomes the page title** and the first paragraph becomes its description, so
  leave both in place.
- **Links between docs** use the plain file name (`[the reference](REFERENCE.md)`); the build
  rewrites them to site routes, with the `/cs` prefix for Czech. Links to code elsewhere in the
  repo are relative and resolve on GitHub too (`../tutorials/01-bounce/`).
- **Don't paste API signatures from memory.** If a change touches an API name, check it against
  `lib/picogame_*.py` in this repo — a name that doesn't exist there fails the pre-publish lint.

## What you cannot preview

The site itself (Astro) is not in this repo, so you cannot render your change locally — GitHub's
markdown preview is what you get. For wording and typo fixes that is enough; for anything
structural, say what you intended in the PR and it gets checked at build time.
