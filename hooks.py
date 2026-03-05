"""
MkDocs hook: auto-generates the blog post index on the homepage.

Each post lives in its own folder: docs/blog/<slug>/index.md
Frontmatter fields:

    ---
    title: My Post Title
    tags: Tag1, Tag2, Tag3
    excerpt: Short description shown on the index card.
    ---

Publication date is read automatically from the first git commit
that added the file (no need to set it manually).

The hook replaces <!-- BLOG_POSTS --> in index.md with a
<div class="post-grid"> of cards, sorted newest-first.
"""

import re
import subprocess
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


def _git_creation_date(filepath: Path, repo_root: Path) -> str:
    """Return YYYY-MM-DD of the first commit that added this file, or ''."""
    try:
        rel = str(filepath.relative_to(repo_root))
        result = subprocess.run(
            ['git', 'log', '--follow', '--format=%cs', '--diff-filter=A', '--', rel],
            capture_output=True, text=True, cwd=str(repo_root),
        )
        lines = [l for l in result.stdout.strip().splitlines() if l]
        # git log is newest-first; last entry = oldest = creation commit
        return lines[-1] if lines else ''
    except Exception:
        return ''


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
            f'<div class="post-title"><a href="{post["url"]}">{post["title"]}</a></div>\n'
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

    docs_dir = Path(config['docs_dir'])
    repo_root = docs_dir.parent
    blog_dir = docs_dir / 'blog'

    if not blog_dir.exists():
        return markdown.replace('<!-- BLOG_POSTS -->', '')

    posts = []
    for post_dir in blog_dir.iterdir():
        if not post_dir.is_dir():
            continue
        index_file = post_dir / 'index.md'
        if not index_file.exists():
            continue

        content = index_file.read_text(encoding='utf-8')
        meta = _parse_frontmatter(content)
        slug = post_dir.name
        date = _git_creation_date(index_file, repo_root)

        posts.append({
            'title': meta.get('title', slug.replace('-', ' ').title()),
            'date': date,
            'tags': [t.strip() for t in meta.get('tags', '').split(',') if t.strip()],
            'excerpt': meta.get('excerpt', ''),
            'url': f'blog/{slug}/',
        })

    # Newest first; posts without date go to the end
    posts.sort(key=lambda p: p['date'] or '0000-00-00', reverse=True)

    grid = _build_grid(posts) if posts else ''
    return markdown.replace('<!-- BLOG_POSTS -->', grid)
