"""
MkDocs hook: blog index, article headers, and Knowledge Base.

Blog posts live in  docs/blog/<slug>/index.md
KB categories live in  docs/kb/<category>/index.md
KB cheat sheets live in  docs/kb/<category>/<sheet>.md

Post frontmatter:
    ---
    title: My Post Title
    type: writeup          # writeup | cve | research
    tags: Tag1, Tag2       # used for KB cross-linking
    excerpt: One line shown on the index card.
    kb_ref: web-security   # optional: KB category slug this post belongs to
    ---

KB category index frontmatter:
    ---
    title: Web Security
    icon: ⚡
    color: web             # maps to --col-web CSS variable
    tags: XSS, SQLi, SSRF  # used to auto-count related posts
    ---

KB cheat sheet frontmatter:
    ---
    title: Cross-Site Scripting (XSS)
    ---
"""

import re
import subprocess
from pathlib import Path

_FRONT_MATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

_TYPE_LABELS = {
    'writeup':  'Writeup',
    'cve':      'CVE',
    'research': 'Research',
}


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────

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
        return lines[-1] if lines else ''
    except Exception:
        return ''


def _get_all_posts(docs_dir: Path, repo_root: Path) -> list:
    """Read metadata for all blog posts, sorted newest-first."""
    blog_dir = docs_dir / 'blog'
    if not blog_dir.exists():
        return []
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
            'title':   meta.get('title', slug.replace('-', ' ').title()),
            'type':    meta.get('type', '').lower().strip(),
            'date':    date,
            'tags':    [t.strip().lower() for t in meta.get('tags', '').split(',') if t.strip()],
            'excerpt': meta.get('excerpt', ''),
            'url':     f'blog/{slug}/',
            'kb_ref':  meta.get('kb_ref', '').strip(),
        })
    posts.sort(key=lambda p: p['date'] or '0000-00-00', reverse=True)
    return posts


def _get_kb_categories(docs_dir: Path, all_posts: list) -> list:
    """Build the KB category list with sheet index and post counts."""
    kb_dir = docs_dir / 'kb'
    if not kb_dir.exists():
        return []
    categories = []
    for cat_dir in sorted(kb_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_index = cat_dir / 'index.md'
        if not cat_index.exists():
            continue
        cat_meta = _parse_frontmatter(cat_index.read_text(encoding='utf-8'))
        cat_slug = cat_dir.name

        # Cheat sheets (flat .md files, not index.md)
        sheets = []
        for f in sorted(cat_dir.iterdir()):
            if f.name == 'index.md' or f.suffix != '.md':
                continue
            sm = _parse_frontmatter(f.read_text(encoding='utf-8'))
            sheets.append({
                'title': sm.get('title', f.stem.replace('-', ' ').title()),
                'url':   f'kb/{cat_slug}/{f.stem}/',
                'slug':  f.stem,
            })

        # Count related blog posts (explicit kb_ref OR tag overlap)
        cat_tags = {t.strip().lower() for t in cat_meta.get('tags', '').split(',') if t.strip()}
        post_count = sum(
            1 for p in all_posts
            if p['kb_ref'] == cat_slug
            or bool(cat_tags & set(p['tags']))
        )

        categories.append({
            'title':      cat_meta.get('title', cat_slug.replace('-', ' ').title()),
            'slug':       cat_slug,
            'icon':       cat_meta.get('icon', '◈'),
            'color':      cat_meta.get('color', 'misc'),
            'url':        f'kb/{cat_slug}/',
            'sheets':     sheets,
            'post_count': post_count,
        })
    return categories


# ──────────────────────────────────────────────────────────
#  Blog index builder
# ──────────────────────────────────────────────────────────

def _build_blog_output(posts: list) -> str:
    present_types, seen = [], set()
    for p in posts:
        t = p['type']
        if t and t not in seen:
            present_types.append(t)
            seen.add(t)

    filter_buttons = '<button class="filter-btn active" data-filter="all">Todos</button>'
    for t in present_types:
        label = _TYPE_LABELS.get(t, t.capitalize())
        filter_buttons += f'\n<button class="filter-btn" data-filter="{t}">{label}</button>'
    filter_bar = f'<div class="filter-bar">\n{filter_buttons}\n</div>'

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


# ──────────────────────────────────────────────────────────
#  KB page builders
# ──────────────────────────────────────────────────────────

def _build_kb_index(categories: list) -> str:
    """Generate the category card grid for the KB homepage."""
    if not categories:
        return '<p>No categories yet.</p>'
    cards = []
    for cat in categories:
        color_var = f'--col-{cat["color"]}'
        sheet_count = len(cat['sheets'])
        sheet_str = f'{sheet_count} sheet{"s" if sheet_count != 1 else ""}'
        post_str  = (f' &nbsp;·&nbsp; <span class="kb-card-posts">● {cat["post_count"]} writeup{"s" if cat["post_count"] != 1 else ""}</span>'
                     if cat['post_count'] else '')

        card = (
            f'<a class="kb-card" href="/{cat["url"]}" style="--cat-color: var({color_var})">\n'
            f'  <span class="kb-card-icon">{cat["icon"]}</span>\n'
            f'  <div class="kb-card-body">\n'
            f'    <div class="kb-card-title">{cat["title"]}</div>\n'
            f'    <div class="kb-card-meta">{sheet_str}{post_str}</div>\n'
            f'  </div>\n'
            f'</a>'
        )
        cards.append(card)
    return '<div class="kb-grid">\n\n' + '\n\n'.join(cards) + '\n\n</div>'


def _build_kb_sheets(docs_dir: Path, cat_slug: str, all_posts: list) -> str:
    """Generate the cheat-sheet card grid + related posts for a KB category page."""
    kb_dir = docs_dir / 'kb' / cat_slug
    cat_index = kb_dir / 'index.md'
    cat_meta  = _parse_frontmatter(cat_index.read_text(encoding='utf-8')) if cat_index.exists() else {}
    cat_tags  = {t.strip().lower() for t in cat_meta.get('tags', '').split(',') if t.strip()}
    color_var = f'--col-{cat_meta.get("color", "misc")}'

    # Cheat sheet cards
    sheet_cards = []
    for f in sorted(kb_dir.iterdir()):
        if f.name == 'index.md' or f.suffix != '.md':
            continue
        sm = _parse_frontmatter(f.read_text(encoding='utf-8'))
        title = sm.get('title', f.stem.replace('-', ' ').title())
        excerpt = sm.get('excerpt', '')
        url = f'/kb/{cat_slug}/{f.stem}/'
        card = (
            f'<a class="kb-sheet-card" href="{url}" style="--cat-color: var({color_var})">\n'
            f'  <div class="kb-sheet-title">{title}</div>\n'
            + (f'  <div class="kb-sheet-excerpt">{excerpt}</div>\n' if excerpt else '')
            + '</a>'
        )
        sheet_cards.append(card)

    grid = ('<div class="kb-sheet-grid">\n\n' + '\n\n'.join(sheet_cards) + '\n\n</div>'
            if sheet_cards else '')

    # Related blog posts
    related = [
        p for p in all_posts
        if p['kb_ref'] == cat_slug or bool(cat_tags & set(p['tags']))
    ]
    related_html = ''
    if related:
        items = []
        for p in related:
            badge = ''
            if p['type']:
                label = _TYPE_LABELS.get(p['type'], p['type'].capitalize())
                badge = f'<span class="post-badge post-badge--{p["type"]}">{label}</span> '
            items.append(
                f'<li><span class="kb-rel-meta">{badge}{p["date"]}</span> '
                f'<a href="{p["url"]}">{p["title"]}</a></li>'
            )
        related_html = (
            '\n\n<div class="kb-related">\n'
            '<div class="kb-related-title">Related posts</div>\n'
            '<ul>\n' + '\n'.join(items) + '\n</ul>\n</div>'
        )

    return grid + related_html


# ──────────────────────────────────────────────────────────
#  MkDocs events
# ──────────────────────────────────────────────────────────

def on_env(env, config, **kwargs):
    """Inject KB nav data into the Jinja2 environment for use in templates."""
    docs_dir = Path(config['docs_dir'])
    repo_root = docs_dir.parent
    all_posts = _get_all_posts(docs_dir, repo_root)
    env.globals['kb_nav'] = _get_kb_categories(docs_dir, all_posts)
    return env


def on_page_content(html, page, config, **kwargs):
    """Inject article meta header (badge + date) on blog post pages."""
    src = page.file.src_path
    if not src.startswith('blog/'):
        return html

    meta = page.meta or {}
    post_type = meta.get('type', '').lower().strip()

    docs_dir  = Path(config['docs_dir'])
    repo_root = docs_dir.parent
    date = _git_creation_date(docs_dir / src, repo_root)

    label = _TYPE_LABELS.get(post_type, post_type.capitalize()) if post_type else ''
    badge     = f'<span class="post-badge post-badge--{post_type}">{label}</span>' if post_type else ''
    date_span = f'<span class="article-date">{date}</span>' if date else ''

    if not badge and not date_span:
        return html

    return f'<div class="article-meta-header">{badge}{date_span}</div>\n' + html


def on_page_markdown(markdown, page, config, **kwargs):
    src = page.file.src_path

    docs_dir  = Path(config['docs_dir'])
    repo_root = docs_dir.parent

    # ── Blog homepage
    if src == 'index.md' and '<!-- BLOG_POSTS -->' in markdown:
        all_posts = _get_all_posts(docs_dir, repo_root)
        output = _build_blog_output(all_posts) if all_posts else ''
        return markdown.replace('<!-- BLOG_POSTS -->', output)

    # ── KB homepage (category overview)
    if src == 'kb/index.md' and '<!-- KB_INDEX -->' in markdown:
        all_posts  = _get_all_posts(docs_dir, repo_root)
        categories = _get_kb_categories(docs_dir, all_posts)
        return markdown.replace('<!-- KB_INDEX -->', _build_kb_index(categories))

    # ── KB category page (cheat-sheet list + related posts)
    if (src.startswith('kb/') and src.endswith('/index.md')
            and src != 'kb/index.md' and '<!-- KB_SHEETS -->' in markdown):
        cat_slug  = src.split('/')[1]
        all_posts = _get_all_posts(docs_dir, repo_root)
        output    = _build_kb_sheets(docs_dir, cat_slug, all_posts)
        return markdown.replace('<!-- KB_SHEETS -->', output)

    return markdown
