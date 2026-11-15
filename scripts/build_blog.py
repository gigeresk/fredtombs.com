# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown-it-py>=3,<4"]
# ///
"""Render markdown blog posts into HTML pages styled like blog-bugfix.html.

Usage: uv run scripts/build_blog.py [post.md ...]

With no arguments, renders every post in POSTS. Each foo.md becomes foo.html
next to it. A post can start with optional front matter:

    ---
    date: October 2026
    description: One-line summary for link previews.
    image: images/thumbs/foo.jpg
    ---

The first "# " heading is the page title. Remaining headings shift down one
level (## -> h3) to match the hand-written pages. An image on its own line
with a title, ![alt](src "caption"), becomes a <figure> with that caption.
A fence whose info string is "c slides a b c" becomes a carousel with one
slide per blank-line-separated chunk, tabbed a, b and c.

Text Claude wrote is marked {++ like this ++} and shows in blue. Markers on
lines of their own wrap whole paragraphs, lists and so on:

    {++
    A paragraph Claude wrote.
    ++}

Delete the markers once the text has been reviewed.
"""

import html
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://fredtombs.com"

VIDEO_EXTENSIONS = (".mp4", ".webm")

# Posts to publish. Drafts stay out of this list until they're ready.
POSTS = [
    "blog-mocarabe-fpga.md",
    "blog-mocarabe-asic.md",
]

TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
   <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>{title} — Fred Tombs</title>
      <meta name="description" content="{description}">
      <meta property="og:title" content="{title}">
      <meta property="og:description" content="{description}">
{image}      <meta name="twitter:card" content="summary">
      <meta name="color-scheme" content="light dark">
      <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
      <meta name="theme-color" content="#161514" media="(prefers-color-scheme: dark)">
      <link rel="icon" type="image/svg+xml" href="favicon.svg">
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,200..900;1,8..60,200..900&display=swap">
      <link rel="stylesheet" href="style.css">
      <script src="zoom.js" defer></script>
   </head>
   <body>
      <!-- Generated from {source} by scripts/build_blog.py. Edit the markdown, not this file. -->
      <header>
         <h1>Fred Tombs</h1>
         <nav>
            <a href="index.html">Home</a>
            <a href="index.html#books">Book Recommendations</a>
            <a href="index.html#friends">Friends</a>
         </nav>
      </header>
      <main>
         <section id="home">
            <h2>{title}</h2>
{date}{body}
         </section>
      </main>
   </body>
</html>
"""


def split_front_matter(text):
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip().lower()] = value.strip()
    return meta, text[match.end():]


C_LANGS = {"c", "cpp", "c++", "cc", "h", "hpp"}

C_KEYWORDS = set("""
    auto bool break case char const constexpr continue default do double else
    enum extern false float for goto if inline int long nullptr register return
    short signed sizeof static struct switch true typedef union unsigned void
    volatile while class namespace template typename using public private
    protected virtual override new delete this NULL size_t
    int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t
""".split())

C_TOKEN = re.compile(
    r"(?P<cm>//.*|/\*.*?(?:\*/|$))"
    r'|(?P<str>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
    r"|(?P<pp>^\s*#\s*\w+)"
    r"|(?P<id>[A-Za-z_]\w*)(?=(?P<call>\s*\()?)"
)


VERILOG_LANGS = {"verilog", "v", "systemverilog", "sv"}

VERILOG_KEYWORDS = set("""
    always always_comb always_ff always_latch assign automatic begin case casex
    casez default deassign else end endcase endfunction endgenerate endmodule
    endtask for force forever function generate genvar if initial inout input
    integer localparam logic module negedge output parameter posedge reg
    release repeat signed task unsigned while wire
""".split())

# Same groups as C_TOKEN, plus "lit" for sized literals (8'hFF, 1'bX), delays
# (#10) and system tasks ($display), which get the c-fn color.
VERILOG_TOKEN = re.compile(
    r"(?P<cm>//.*|/\*.*?(?:\*/|$))"
    r'|(?P<str>"(?:\\.|[^"\\])*")'
    r"|(?P<pp>`\w+)"
    r"|(?P<lit>\d*'[sS]?[bBoOdDhH][0-9a-fA-FxXzZ_?]+|#\d+|\$\w+)"
    r"|(?P<id>[A-Za-z_]\w*)(?=(?P<call>\s*\()?)"
)


def highlight_c(lines, token=C_TOKEN, keywords=C_KEYWORDS):
    """Wrap keywords, function names and comments in the c-kw, c-fn and c-cm
    spans that blog-bugfix.html uses. Returns escaped HTML lines. C by
    default; pass VERILOG_TOKEN and VERILOG_KEYWORDS for Verilog."""
    out = []
    in_comment = False
    for line in lines:
        parts = []
        pos = 0
        if in_comment:
            end = line.find("*/")
            pos = len(line) if end < 0 else end + 2
            parts.append(f'<span class="c-cm">{html.escape(line[:pos], quote=False)}</span>')
            in_comment = end < 0
        for m in token.finditer(line, pos):
            parts.append(html.escape(line[pos : m.start()], quote=False))
            text = html.escape(m.group(0), quote=False)
            if m.group("cm"):
                parts.append(f'<span class="c-cm">{text}</span>')
                in_comment = m.group(0).startswith("/*") and not m.group(0).endswith("*/")
            elif m.group("pp"):
                parts.append(f'<span class="c-kw">{text}</span>')
            elif m.groupdict().get("lit"):
                parts.append(f'<span class="c-fn">{text}</span>')
            elif m.group("id") and m.group("id") in keywords:
                parts.append(f'<span class="c-kw">{text}</span>')
            elif m.group("id") and m.group("call") is not None:
                parts.append(f'<span class="c-fn">{text}</span>')
            else:
                parts.append(text)
            pos = m.end()
        parts.append(html.escape(line[pos:], quote=False))
        out.append("".join(parts))
    return out


def code_table(text, lang=""):
    # Match the hand-written code tables in blog-bugfix.html.
    lines = text.rstrip("\n").split("\n")
    if lang.lower() in C_LANGS:
        cells = highlight_c(lines)
    elif lang.lower() in VERILOG_LANGS:
        cells = highlight_c(lines, VERILOG_TOKEN, VERILOG_KEYWORDS)
    else:
        cells = [html.escape(line, quote=False) for line in lines]
    rows = "".join(f'<tr><td class="cd">{cell or " "}</td></tr>\n' for cell in cells)
    return f'<table class="c-block no-ln">\n{rows}</table>\n'


# Swipe the track, click a tab, or use the arrow keys on the tabs. Without
# JavaScript the track still scrolls sideways and snaps to each slide.
SLIDES_SCRIPT = """\
<script>
document.querySelectorAll(".code-slides").forEach((box) => {
  const track = box.querySelector(".code-slides-track");
  const slides = [...track.children];
  const tabs = [...box.querySelectorAll(".code-slides-tabs button")];
  const go = (i) => track.scrollTo({ left: slides[i].offsetLeft, behavior: "smooth" });
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => go(i));
    tab.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (!step) return;
      const next = (i + step + tabs.length) % tabs.length;
      tabs[next].focus();
      go(next);
    });
  });
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const i = slides.indexOf(entry.target);
      const bar = tabs[i].parentElement;
      bar.scrollTo({ left: tabs[i].offsetLeft - (bar.clientWidth - tabs[i].offsetWidth) / 2, behavior: "smooth" });
      tabs.forEach((tab, j) => {
        tab.setAttribute("aria-selected", i === j);
        tab.tabIndex = i === j ? 0 : -1;
      });
    });
  }, { root: track, threshold: 0.6 });
  slides.forEach((slide) => seen.observe(slide));
});
</script>
"""


def render_slides(token, lang, labels, env):
    """A fence like ```c slides fig3 poly3 becomes a swipeable carousel.

    The block is split on blank lines, one slide per chunk, and each chunk
    gets the matching label as its tab.
    """
    chunks = [c for c in re.split(r"\n\s*\n", token.content.strip("\n")) if c.strip()]
    if len(labels) != len(chunks):
        sys.exit(
            f"slides block at line {token.map[0] + 1}: {len(labels)} labels "
            f"for {len(chunks)} chunks"
        )
    tabs = "".join(
        f'<button type="button" role="tab" aria-selected="true">{html.escape(label)}</button>'
        if i == 0
        else f'<button type="button" role="tab" aria-selected="false" tabindex="-1">'
        f"{html.escape(label)}</button>"
        for i, label in enumerate(labels)
    )
    slides = "".join(
        f'<div class="slide" role="tabpanel" aria-label="{html.escape(label)}">\n'
        f"{code_table(chunk, lang)}</div>\n"
        for label, chunk in zip(labels, chunks)
    )
    env["slides_script"] = SLIDES_SCRIPT
    return (
        f'<div class="code-slides">\n<div class="code-slides-tabs" role="tablist">{tabs}</div>\n'
        f'<div class="code-slides-track">\n{slides}</div>\n</div>\n'
    )


def render_code_block(self, tokens, idx, options, env):
    words = tokens[idx].info.split()
    if len(words) >= 2 and words[1] == "slides":
        return render_slides(tokens[idx], words[0], words[2:], env)
    return code_table(tokens[idx].content, words[0] if words else "")


def shift_heading(self, tokens, idx, options, env):
    token = tokens[idx]
    level = min(int(token.tag[1]) + 1, 6)
    token.tag = f"h{level}"
    return self.renderToken(tokens, idx, options, env)


md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
md.add_render_rule("fence", render_code_block)
md.add_render_rule("code_block", render_code_block)
md.add_render_rule("heading_open", shift_heading)
md.add_render_rule("heading_close", shift_heading)


def make_figures(tokens):
    """Turn a paragraph holding only ![alt](src "caption") into <figure>.

    The caption is rendered as inline markdown, so it can hold links.  A video
    source (.mp4, .webm) becomes a muted, looping <video> instead of an <img>.
    """
    out = []
    i = 0
    while i < len(tokens):
        children = tokens[i + 1].children if i + 1 < len(tokens) else None
        if (
            tokens[i].type == "paragraph_open"
            and children
            and len(children) == 1
            and children[0].type == "image"
            and children[0].attrGet("title")
        ):
            image = children[0]
            caption = md.renderInline(image.attrGet("title"))
            src = html.escape(image.attrGet("src"))
            alt = html.escape(plain_text(image))
            if src.lower().endswith(VIDEO_EXTENSIONS):
                media = (
                    f'<video src="{src}" aria-label="{alt}" autoplay loop muted playsinline '
                    'controls preload="metadata"></video>'
                )
            else:
                media = f'<img src="{src}" alt="{alt}" loading="lazy">'
            figure = Token("html_block", "", 0)
            figure.content = f"<figure>\n{media}\n<figcaption>{caption}</figcaption>\n</figure>\n"
            out.append(figure)
            i += 3
        else:
            out.append(tokens[i])
            i += 1
    return out


def drop_comments(tokens):
    """Leave <!-- ... --> blocks out of the page, so commented-out drafts
    don't ship in the HTML source."""
    return [
        t
        for t in tokens
        if not (
            t.type == "html_block"
            and t.content.strip().startswith("<!--")
            and t.content.strip().endswith("-->")
        )
    ]


def plain_text(inline_token):
    return "".join(
        child.content for child in inline_token.children or [] if child.type in ("text", "code_inline")
    )


CLAUDE_OPEN = "{++"
CLAUDE_CLOSE = "++}"


def mark_claude_text(text):
    """Turn {++ ... ++} markers into blue <div>/<span class="claude"> wrappers.

    A marker alone on a line wraps blocks; any other marker wraps inline text
    in the same paragraph. Lines inside code fences are left alone.
    """
    out = []
    fence = None
    for line in text.split("\n"):
        stripped = line.strip()
        match = re.match(r"(`{3,}|~{3,})", stripped)
        if fence:
            if match and stripped.startswith(fence) and not stripped[len(fence):].strip():
                fence = None
            out.append(line)
        elif match:
            fence = match.group(1)
            out.append(line)
        elif stripped == CLAUDE_OPEN:
            out += ['<div class="claude">', ""]
        elif stripped == CLAUDE_CLOSE:
            out += ["", "</div>"]
        else:
            line = line.replace(CLAUDE_OPEN, '<span class="claude">')
            out.append(line.replace(CLAUDE_CLOSE, "</span>"))
    return "\n".join(out)


def build(source):
    meta, text = split_front_matter(source.read_text())
    text = mark_claude_text(text)
    tokens = md.parse(text)

    title = meta.get("title")
    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag == "h1":
            title = title or plain_text(tokens[i + 1])
            del tokens[i : i + 3]
            break
    if not title:
        sys.exit(f"{source.name}: needs a '# Title' heading or a title in front matter")

    description = meta.get("description")
    if not description:
        first_para = next((t for t in tokens if t.type == "inline"), None)
        description = plain_text(first_para) if first_para else title
        if len(description) > 160:
            description = description[:157].rsplit(" ", 1)[0] + "..."

    tokens = make_figures(drop_comments(tokens))
    date = f"            <p><em>{html.escape(meta['date'])}</em></p>\n" if "date" in meta else ""
    image = (
        f'      <meta property="og:image" content="{SITE}/{html.escape(meta["image"])}">\n'
        if "image" in meta
        else ""
    )
    env = {}
    body = md.renderer.render(tokens, md.options, env)
    body += env.get("slides_script", "")

    out = source.with_suffix(".html")
    out.write_text(
        TEMPLATE.format(
            title=html.escape(title),
            description=html.escape(" ".join(description.split())),
            source=source.name,
            date=date,
            image=image,
            body=body,
        )
    )
    print(f"{source.name} -> {out.name}")


def main():
    sources = [Path(arg).resolve() for arg in sys.argv[1:]] or [ROOT / name for name in POSTS]
    for source in sources:
        build(source)


if __name__ == "__main__":
    main()
