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
    ---

The first "# " heading is the page title. Remaining headings shift down one
level (## -> h3) to match the hand-written pages. An image on its own line
with a title, ![alt](src "caption"), becomes a <figure> with that caption.
"""

import html
import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

ROOT = Path(__file__).resolve().parent.parent

VIDEO_EXTENSIONS = (".mp4", ".webm")

# Posts to publish. Drafts stay out of this list until they're ready.
POSTS = [
    "blog-mocarabe-fpga.md",
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
      <meta name="twitter:card" content="summary">
      <meta name="color-scheme" content="light dark">
      <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
      <meta name="theme-color" content="#161514" media="(prefers-color-scheme: dark)">
      <link rel="icon" type="image/svg+xml" href="favicon.svg">
      <link rel="stylesheet" href="style.css">
   </head>
   <body>
      <!-- Generated from {source} by scripts/build_blog.py. Edit the markdown, not this file. -->
      <header>
         <h1>
            <a href="index.html">Fred Tombs</a>
         </h1>
         <nav>
            <a href="index.html#projects">Projects</a>
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


def render_code_block(self, tokens, idx, options, env):
    # Match the hand-written code tables in blog-bugfix.html.
    lines = tokens[idx].content.rstrip("\n").split("\n")
    rows = "".join(
        f'<tr><td class="cd">{html.escape(line, quote=False) or " "}</td></tr>\n'
        for line in lines
    )
    return f'<table class="c-block no-ln">\n{rows}</table>\n'


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


def plain_text(inline_token):
    return "".join(
        child.content for child in inline_token.children or [] if child.type in ("text", "code_inline")
    )


def build(source):
    meta, text = split_front_matter(source.read_text())
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

    tokens = make_figures(tokens)
    date = f"            <p><em>{html.escape(meta['date'])}</em></p>\n" if "date" in meta else ""
    body = md.renderer.render(tokens, md.options, {})

    out = source.with_suffix(".html")
    out.write_text(
        TEMPLATE.format(
            title=html.escape(title),
            description=html.escape(" ".join(description.split())),
            source=source.name,
            date=date,
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
