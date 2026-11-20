# arabic-readiness

One number for the question every team asks when Arabic enters the roadmap: **are we ready?**

It runs two linters, combines three signals, and leaves a single comment on the pull request.

```
## Arabic readiness: 36%

**not ready** · physical layout code in 1 of 1 files · 2 of 3 keys translated

| Check | Score | Detail |
| --- | --- | --- |
| RTL layout | 0% | physical layout code in 1 of 1 files |
| Arabic coverage | 67% | 2 of 3 keys translated |
| Placeholders & plurals | 90% | 1 placeholder or plural issue |
```

## Use

```yaml
name: Arabic readiness

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hfip/arabic-readiness@v1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
```

The comment is created once and updated in place on every push, so the PR does not fill up
with stale numbers.

## What is scored

| Dimension | Weight | Source |
| --- | --- | --- |
| RTL layout | 0.5 | share of Swift/storyboard files with no physical `left`/`right` code ([rtl-lint](https://github.com/hfip/rtl-lint)) |
| Arabic coverage | 0.4 | translated keys in the String Catalog ([xcstrings-audit](https://github.com/hfip/xcstrings-audit)) |
| Placeholders & plurals | 0.1 | placeholder and plural problems, 10 points each |

```
score = 0.5 × layout + 0.4 × coverage + 0.1 × consistency
```

If the catalog or the language is missing, those dimensions are dropped and the remaining
weights are renormalised, so a UIKit-only repository still gets a meaningful number. The
comment always prints the arithmetic it used.

Status bands: `ready` at 90 and above, `almost there` at 70, `not ready` below.

## Inputs

| Input | Default | Notes |
| --- | --- | --- |
| `token` | required | `${{ secrets.GITHUB_TOKEN }}` with `issues: write` |
| `paths` | `Sources` | what `rtl-lint` scans |
| `catalog-paths` | same as `paths` | where `.xcstrings` files live |
| `lang` | `ar` | language to score coverage for |
| `comment` | `true` | post the PR comment |
| `min-score` | `0` | fail the job below this score |
| `rtl-lint-ref` | `v1` | pin the linter version |
| `xcstrings-audit-ref` | `v0.1.1` | pin the catalog checker |

Outputs: `score` (0–100).

```yaml
- uses: hfip/arabic-readiness@v1
  id: arabic
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    paths: app/Sources
    catalog-paths: app/Resources
    min-score: "70"
- run: echo "Arabic readiness is ${{ steps.arabic.outputs.score }}"
```

`min-score` is off by default on purpose: a new number on a PR should start conversations,
not block merges.

## What it does not check

- Images that must mirror (back arrows, timelines, media controls).
- Number, date and currency formatting.
- Truncation and line breaking in Arabic, where strings are often longer.
- Whether the translation reads well. This measures structure, not language quality.

The score is a nudge with a paper trail, not a certification.

## بالعربي

<div dir="rtl" align="right">

أداة واحدة تجيب سؤال «هل التطبيق جاهز للعربية؟» بتعليق واحد على الـ PR:

```yaml
- uses: hfip/arabic-readiness@v1
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
```

تجمع ثلاث نقاط: نسبة ملفات الواجهة النظيفة من `left/right`، ونسبة الترجمة، وأخطاء
البلاسهولدرات والجمع. والدرجة تُحسب بمعادلة مكتوبة في التعليق نفسه، مو رقم غامض.

</div>

## License

MIT. See [LICENSE](LICENSE).
