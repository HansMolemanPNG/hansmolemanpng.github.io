"""
MkDocs hook — data provider for the custom theme.

Reads content metadata and injects it as Jinja2 globals so templates
can render everything without Python generating HTML strings.

Post frontmatter:
    ---
    title: My Post Title
    type: writeup | cve | research
    tags: Tag1, Tag2
    excerpt: Text shown on index cards. Supports multi-line (YAML block scalar |) and markdown.
    kb_ref: web-security/xss   # optional: links to a specific KB sheet
    ---

KB category index frontmatter (docs/kb/<category>/index.md):
    ---
    title: Web Security
    icon: ⚡
    color: web             # maps to --col-web CSS variable
    ---

KB cheat sheet frontmatter (docs/kb/<category>/<sheet>.md):
    ---
    title: Cross-Site Scripting (XSS)
    excerpt: Optional description. Supports multi-line (YAML block scalar |) and markdown.
    tags: XSS, Reflected, DOM
    ---
"""

import re
import subprocess
from pathlib import Path

import markdown as _md_lib
import yaml

_FRONT_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)

_TYPE_LABELS = {
    'writeup':  'Writeup',
    'cve':      'CVE',
    'research': 'Research',
}

_GROUP_ORDER = ['web', 'lowlevel', 'other']
_GROUP_LABELS = {
    'web':      'Web Security',
    'lowlevel': 'Low Level',
    'other':    'General',
}


# ── Helpers ────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict:
    m = _FRONT_RE.match(content)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}
    return {str(k).lower(): v for k, v in data.items()}


def _excerpt_html(text) -> str:
    if not text:
        return ''
    return _md_lib.markdown(str(text).strip(), extensions=['nl2br'])


def _git_date(filepath: Path, repo_root: Path) -> str:
    """First commit date for a file, as YYYY-MM-DD."""
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
    """All blog posts, sorted newest-first."""
    blog_dir = docs_dir / 'blog'
    if not blog_dir.exists():
        return []

    posts = []
    for post_dir in blog_dir.iterdir():
        if not post_dir.is_dir():
            continue
        index = post_dir / 'index.md'
        if not index.exists():
            continue
        meta = _parse_frontmatter(index.read_text(encoding='utf-8'))
        slug = post_dir.name
        t = str(meta.get('type', '')).lower().strip()
        raw_tags = meta.get('tags', '')
        tags = raw_tags if isinstance(raw_tags, list) else [s.strip() for s in str(raw_tags).split(',') if s.strip()]
        excerpt = meta.get('excerpt', '')
        posts.append({
            'title':        meta.get('title', slug.replace('-', ' ').title()),
            'type':         t,
            'label':        _TYPE_LABELS.get(t, t.capitalize()),
            'date':         _git_date(index, repo_root),
            'tags':         tags,
            'excerpt':      excerpt,
            'excerpt_html': _excerpt_html(excerpt),
            'url':          f'blog/{slug}/',
            'kb_ref':       str(meta.get('kb_ref', '')).strip(),
        })

    posts.sort(key=lambda p: p['date'] or '0000-00-00', reverse=True)
    return posts


def _get_kb_categories(docs_dir: Path, all_posts: list) -> list:
    """KB categories with per-sheet post lists."""
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

        sheets = []
        for f in sorted(cat_dir.iterdir()):
            if f.name == 'index.md' or f.suffix != '.md':
                continue
            sm = _parse_frontmatter(f.read_text(encoding='utf-8'))
            sheet_ref = f'{cat_slug}/{f.stem}'
            sheet_posts = [p for p in all_posts if p['kb_ref'] == sheet_ref]
            cs = sm.get('coming_soon', False)
            coming_soon = cs if isinstance(cs, bool) else str(cs).lower() in ('true', '1', 'yes')
            excerpt = sm.get('excerpt', '')
            raw_tags = sm.get('tags', '')
            tags = raw_tags if isinstance(raw_tags, list) else [s.strip() for s in str(raw_tags).split(',') if s.strip()]
            sheets.append({
                'title':        sm.get('title', f.stem.replace('-', ' ').title()),
                'excerpt':      excerpt,
                'excerpt_html': _excerpt_html(excerpt),
                'tags':         tags,
                'url':          f'kb/{cat_slug}/{f.stem}/',
                'slug':         f.stem,
                'posts':        sheet_posts,
                'coming_soon':  coming_soon,
            })

        group_raw = cat_meta.get('group', 'other').lower().strip()
        categories.append({
            'title':       cat_meta.get('title', cat_slug.replace('-', ' ').title()),
            'slug':        cat_slug,
            'icon':        cat_meta.get('icon', '◈'),
            'color':       cat_meta.get('color', 'misc'),
            'url':         f'kb/{cat_slug}/',
            'sheets':      sheets,
            'post_count':  sum(len(s['posts']) for s in sheets),
            'group':       group_raw,
            'group_label': _GROUP_LABELS.get(group_raw, group_raw.title()),
        })

    return categories


# ── MkDocs events ──────────────────────────────────────────────

def on_env(env, config, **kwargs):
    """Inject all_posts and kb_categories as Jinja2 globals."""
    docs_dir  = Path(config['docs_dir'])
    repo_root = docs_dir.parent
    all_posts     = _get_all_posts(docs_dir, repo_root)
    kb_categories = _get_kb_categories(docs_dir, all_posts)
    env.globals['all_posts']     = all_posts
    env.globals['kb_categories'] = kb_categories
    env.globals['kb_group_order']  = _GROUP_ORDER
    env.globals['kb_group_labels'] = _GROUP_LABELS
    return env


def on_page_markdown(markdown, page, config, **kwargs):
    """Auto-assign templates based on page path (before MkDocs resolves the template)."""
    src = page.file.src_path
    if not page.meta.get('template'):
        if src.startswith('blog/') and src != 'blog/index.md':
            page.meta['template'] = 'blog-post.html'
        elif src.startswith('kb/') and src.endswith('/index.md') and src != 'kb/index.md':
            page.meta['template'] = 'kb-category.html'
        elif src.startswith('kb/') and src != 'kb/index.md':
            page.meta['template'] = 'kb-sheet.html'
    return markdown


def on_page_content(html, page, config, **kwargs):
    """Inject post meta header (type badge + date) on blog posts."""
    src = page.file.src_path
    if not src.startswith('blog/') or src == 'blog/index.md':
        return html

    meta      = page.meta or {}
    post_type = meta.get('type', '').lower().strip()
    docs_dir  = Path(config['docs_dir'])
    repo_root = docs_dir.parent
    date      = _git_date(docs_dir / src, repo_root)

    label = _TYPE_LABELS.get(post_type, '') if post_type else ''
    badge = (f'<span class="badge badge--{post_type}">{label}</span>'
             if label else '')
    date_el = f'<time class="post-date">{date}</time>' if date else ''

    if not badge and not date_el:
        return html

    return f'<div class="post-meta-hdr">{badge}{date_el}</div>\n' + html
