# picogame documentation

The pages behind <https://picogame.makerclass.cz>. Edit one, open a pull request — typos, clearer
wording, a missing warning, a translation are all welcome.

## What is where

| Path | What it is |
|---|---|
| `*.md` | one page each, English — **the file name is the route** (`reference.md` → `/reference/`) |
| `cs/*.md` | the Czech translation, same file name (`cs/reference.md`). Missing ones fall back to English |
| `pages/**.md` | pages written directly for the site (concepts, helpers, quickstart); they already carry Starlight frontmatter |
| `pages/cs/**.md` | their Czech counterparts |
| `img/`, `audio/` | published assets; reference them as `img/name.png` (from `cs/`, `../img/name.png`) |

A few pages embed live components (the playground, the scene editor, the tutorial walkthroughs);
those live with the site code and are not here.

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
- **Links between docs** use the plain file name (`[the reference](reference.md)`); the build
  rewrites them to site routes, with the `/cs` prefix for Czech. Links to code elsewhere in the
  repo are relative and resolve on GitHub too (`../tutorials/01-bounce/`).
- **Don't paste API signatures from memory.** If a change touches an API name, check it against
  `lib/picogame_*.py` in this repo — a name that doesn't exist there fails the pre-publish lint.

## Previewing

There is no local preview — GitHub's markdown rendering is what you get. That is enough for wording
and typos; if a change is structural, say what you intended in the PR.
