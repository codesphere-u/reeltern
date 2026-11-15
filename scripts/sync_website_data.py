"""Sync machine-readable MCP schemas and compact GitHub release metadata into website/."""
import argparse
import json
import os
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPO = 'codesphere-u/reeltern'


def compact_release(rel: dict) -> dict:
    return {
        'tag_name': rel.get('tag_name', ''),
        'name': rel.get('name') or rel.get('tag_name', ''),
        'prerelease': bool(rel.get('prerelease', False)),
        'draft': bool(rel.get('draft', False)),
        'published_at': rel.get('published_at') or rel.get('created_at', ''),
        'html_url': rel.get('html_url', f'https://github.com/{REPO}/releases'),
        'tarball_url': rel.get('tarball_url', ''),
        'zipball_url': rel.get('zipball_url', ''),
        'body': rel.get('body') or '',
        'assets': [
            {
                'name': a.get('name', ''),
                'size': int(a.get('size', 0) or 0),
                'digest': a.get('digest') or '',
                'download_count': int(a.get('download_count', 0) or 0),
                'updated_at': a.get('updated_at', ''),
                'browser_download_url': a.get('browser_download_url', ''),
            }
            for a in (rel.get('assets') or [])
        ],
    }


def fetch_releases(repo: str, token: str | None = None) -> list[dict]:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{repo}/releases?per_page=20',
        headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'reeltern-pages-sync',
            **({'Authorization': f'Bearer {token}'} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    if not isinstance(data, list):
        return []
    return [compact_release(item) for item in data if not item.get('draft')]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Fetch live releases from GitHub API')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', REPO))
    args = parser.parse_args()

    web = ROOT / 'website'
    web.mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'docs' / 'mcp-tools.json', web / 'mcp-tools.json')

    rel_path = web / 'releases.json'
    if args.fetch:
        releases = fetch_releases(args.repo, os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'))
        rel_path.write_text(json.dumps(releases, indent=2) + '\n', encoding='utf-8')
        print(f'Synced mcp-tools.json and {len(releases)} GitHub release(s) to {rel_path}')
    elif rel_path.exists():
        raw = json.loads(rel_path.read_text(encoding='utf-8'))
        if isinstance(raw, list):
            compacted = [compact_release(item) for item in raw if not item.get('draft')]
            rel_path.write_text(json.dumps(compacted, indent=2) + '\n', encoding='utf-8')
            print(f'Compacted {len(compacted)} cached release(s) in {rel_path}')


if __name__ == '__main__':
    main()
