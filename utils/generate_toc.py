"""Generate notebook tables of contents for the English and Chinese trees."""

import argparse
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('zh', 'en')
COLAB_BADGE = (
    '[![Open In Colab]'
    '(https://colab.research.google.com/assets/colab-badge.svg)]'
    '({url})'
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Generate zh/README.md and en/README.md from notebook file names.'
    )
    parser.add_argument(
        '--github-repo',
        help='GitHub repository in owner/name form. Inferred from origin when omitted.',
    )
    parser.add_argument(
        '--branch',
        help='Git branch for Colab links. Inferred from the current branch when omitted.',
    )
    return parser.parse_args()


def run_git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError, subprocess.CalledProcessError:
        return None
    return result.stdout.strip()


def infer_github_repo(root: Path) -> str | None:
    github_repository = os.environ.get('GITHUB_REPOSITORY')
    if github_repository:
        return github_repository

    remote_url = run_git(['remote', 'get-url', 'origin'], root)
    if not remote_url:
        return None

    patterns = (
        r'github\.com[:/](?P<repo>[^/]+/[^/.]+)(?:\.git)?$',
        r'github\.com/(?P<repo>[^/]+/[^/.]+)(?:\.git)?$',
    )
    for pattern in patterns:
        match = re.search(pattern, remote_url)
        if match:
            return match.group('repo')
    return None


def infer_branch(root: Path) -> str:
    branch = run_git(['branch', '--show-current'], root)
    return branch or 'main'


def git_visible_files(root: Path, language: str) -> set[Path] | None:
    output = run_git(
        ['ls-files', '--cached', '--others', '--exclude-standard', '--', language],
        root,
    )
    if output is None:
        return None
    return {Path(line) for line in output.splitlines()}


def natural_key(path: Path) -> list[int | str]:
    rel_path = path.as_posix()
    parts = re.split(r'(\d+)', rel_path)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def title_from_path(path: Path, language: str) -> str:
    return path.relative_to(language).with_suffix('').name


def colab_url(github_repo: str, branch: str, path: Path) -> str:
    rel_path = path.as_posix()
    return f'https://colab.research.google.com/github/{github_repo}/blob/{branch}/{rel_path}'


def collect_notebooks(root: Path, language: str) -> list[Path]:
    language_root = root / language
    visible_files = git_visible_files(root, language)
    notebooks = []
    paths = (
        visible_files if visible_files is not None else language_root.rglob('*.ipynb')
    )
    for path in paths:
        if path.suffix != '.ipynb':
            continue
        if path.name == 'README.ipynb':
            continue
        notebooks.append(path if visible_files is not None else path.relative_to(root))
    return sorted(notebooks, key=natural_key)


def chapter_title(path: Path, language: str) -> str:
    rel_path = path.relative_to(language)
    if len(rel_path.parts) < 2:
        return 'Notebooks'
    return rel_path.parts[0]


def generate_readme(
    root: Path,
    language: str,
    notebooks: list[Path],
    github_repo: str,
    branch: str,
) -> str:
    lines = ['# Table of Contents', '']
    current_chapter = None

    for notebook in notebooks:
        chapter = chapter_title(notebook, language)
        if chapter != current_chapter:
            if current_chapter is not None:
                lines.append('')
            lines.extend([f'## {chapter}', '', '| File | Colab |', '| :---: | :---: |'])
            current_chapter = chapter

        title = title_from_path(notebook, language)
        badge = COLAB_BADGE.format(url=colab_url(github_repo, branch, notebook))
        notebook_link = notebook.relative_to(language).as_posix()
        lines.append(f'| [{title}]({notebook_link}) | {badge} |')

    if not notebooks:
        lines.append('_No notebooks found._')

    return '\n'.join(lines).rstrip() + '\n'


def main() -> None:
    args = parse_args()
    github_repo = args.github_repo or infer_github_repo(ROOT)
    branch = args.branch or infer_branch(ROOT)

    if not github_repo:
        raise SystemExit(
            'Could not infer a GitHub repository. Pass --github-repo OWNER/REPO.'
        )

    for language in LANGUAGES:
        notebooks = collect_notebooks(ROOT, language)
        if not notebooks and not (ROOT / language).exists():
            continue

        readme = generate_readme(ROOT, language, notebooks, github_repo, branch)

        file = ROOT / language / 'README.md'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(readme, encoding='utf-8')


if __name__ == '__main__':
    main()
