"""
MkDocs hook: auto-generates the blog post index on the homepage.

Each post lives in its own folder: docs/blog/<slug>/index.md
Frontmatter fields:

    ---
    title: My Post Title
    type: writeup          # one of: writeup, cve, research
    tags: Tag1, Tag2, Tag3
    excerpt: Short description shown on the index card.
    ---

Publication date is read automatically from the first git commit
that added the file (no need to set it manually).

The hook replaces <!-- BLOG_POSTS --> in index.md with filter
buttons followed by a <div class="post-grid"> of cards, sorted
newest-first.
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


_TYPE_LABELS = {
    'writeup':  'Writeup',
    'cve':      'CVE',
    'research': 'Research',
}


def _build_output(posts: list) -> str:
    # Collect types present in posts to build filter buttons
    present_types = []
    seen = set()
    for p in posts:
        t = p['type']
        if t and t not in seen:
            present_types.append(t)
            seen.add(t)

    # Filter bar (always rendered; hidden via CSS if only one type exists)
    filter_buttons = '<button class="filter-btn active" data-filter="all">Todos</button>'
    for t in present_types:
        label = _TYPE_LABELS.get(t, t.capitalize())
        filter_buttons += f'\n<button class="filter-btn" data-filter="{t}">{label}</button>'
    filter_bar = f'<div class="filter-bar">\n{filter_buttons}\n</div>'

    # Cards
    cards = []
    for post in posts:
        tags_str = ' · '.join(post['tags']) if post['tags'] else ''
        meta_parts = []
        if post['date']:
            meta_parts.append(post['date'])
        if tags_str:
            meta_parts.append(f'Tags: {tags_str}')
        meta_html = ' &nbsp;·&nbsp; '.join(meta_parts)

        badge = ''
        if post['type']:
            label = _TYPE_LABELS.get(post['type'], post['type'].capitalize())
            badge = f'<span class="post-badge post-badge--{post["type"]}">{label}</span>\n'

        card = (
            f'<div class="post-card" data-type="{post["type"]}">\n'
            + badge
            + f'<div class="post-title"><a href="{post["url"]}">{post["title"]}</a></div>\n'
            + (f'<div class="post-meta">{meta_html}</div>\n' if meta_html else '')
            + (f'<div class="post-excerpt">{post["excerpt"]}</div>\n' if post['excerpt'] else '')
            + '</div>'
        )
        cards.append(card)

    grid = '<div class="post-grid">\n\n' + '\n\n'.join(cards) + '\n\n</div>' if cards else ''
    return filter_bar + '\n\n' + grid


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
            'type': meta.get('type', '').lower().strip(),
            'date': date,
            'tags': [t.strip() for t in meta.get('tags', '').split(',') if t.strip()],
            'excerpt': meta.get('excerpt', ''),
            'url': f'blog/{slug}/',
        })

    # Newest first; posts without date go to the end
    posts.sort(key=lambda p: p['date'] or '0000-00-00', reverse=True)

    output = _build_output(posts) if posts else ''
    return markdown.replace('<!-- BLOG_POSTS -->', output)
