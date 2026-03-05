"""
MkDocs hook: auto-generates the blog post index on the homepage.

Each .md file inside docs/blog/ should include YAML frontmatter:

    ---
    title: My Post Title
    date: 2024-03-01
    tags: Tag1, Tag2, Tag3
    excerpt: Short description shown on the index card.
    ---

The hook replaces the <!-- BLOG_POSTS --> comment in index.md with
a <div class="post-grid"> of cards, sorted newest-first by date.
"""

import re
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def _parse_frontmatter(content: str) -> dict:
    match = _FRONT_MATTER_RE.match(content)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        if ':' in line:
            key, _, value = line.partition(':')
            meta[key.strip().lower()] = value.strip()
    return meta


def _build_grid(posts: list) -> str:
    cards = []
    for post in posts:
        tags_str = ' · '.join(post['tags']) if post['tags'] else ''
        meta_parts = []
        if post['date']:
            meta_parts.append(post['date'])
        if tags_str:
            meta_parts.append(f'Tags: {tags_str}')
        meta_html = ' &nbsp;·&nbsp; '.join(meta_parts)

        card = (
            '<div class="post-card">\n'
            f'<h3><a href="{post["url"]}">{post["title"]}</a></h3>\n'
            + (f'<div class="post-meta">{meta_html}</div>\n' if meta_html else '')
            + (f'<div class="post-excerpt">{post["excerpt"]}</div>\n' if post['excerpt'] else '')
            + '</div>'
        )
        cards.append(card)

    return '<div class="post-grid">\n\n' + '\n\n'.join(cards) + '\n\n</div>'


def on_page_markdown(markdown, page, config, **kwargs):
    if page.file.src_path != 'index.md':
        return markdown
    if '<!-- BLOG_POSTS -->' not in markdown:
        return markdown

    blog_dir = Path(config['docs_dir']) / 'blog'
    if not blog_dir.exists():
        return markdown.replace('<!-- BLOG_POSTS -->', '')

    posts = []
    for md_file in blog_dir.glob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        meta = _parse_frontmatter(content)
        slug = md_file.stem
        posts.append({
            'title': meta.get('title', slug.replace('-', ' ').title()),
            'date': meta.get('date', ''),
            'tags': [t.strip() for t in meta.get('tags', '').split(',') if t.strip()],
            'excerpt': meta.get('excerpt', ''),
            'url': f'blog/{slug}/',
        })

    # Sort newest first; posts without date go last
    posts.sort(key=lambda p: p['date'], reverse=True)

    grid = _build_grid(posts) if posts else ''
    return markdown.replace('<!-- BLOG_POSTS -->', grid)
