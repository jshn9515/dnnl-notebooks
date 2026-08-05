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
    """Run a git command and return its output, or None if git is not available or
    the command fails.
    """
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except FileNotFoundError, subprocess.CalledProcessError:
        return None


def infer_github_repo(root: Path) -> str | None:
    """Infer the GitHub repository from the git remote URL or the GITHUB_REPOSITORY
    environment variable.
    """
    repo = os.environ.get('GITHUB_REPOSITORY')
    if repo:
        return repo

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
    """Infer the current git branch, or return 'main' if it cannot be determined."""
    branch = run_git(['branch', '--show-current'], root)
    return branch or 'main'


def git_visible_files(root: Path, language: str) -> set[Path] | None:
    """Return a set of files that are visible to git in the given language tree, or None
    if git is not available or the command fails.
    """
    args = ['ls-files', '--cached', '--others', '--exclude-standard', '--', language]
    output = run_git(args, cwd=root)
    if output is None:
        return None
    return {Path(line) for line in output.splitlines()}


def natural_key(path: Path) -> list[int | str]:
    """Return a key for natural sorting of paths, where numeric parts are sorted
    numerically and non-numeric parts are sorted case-insensitively.
    """
    rel_path = path.as_posix()
    parts = re.split(r'(\d+)', rel_path)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def title_from_path(path: Path, language: str) -> str:
    """Return a title for the notebook based on its path relative to the language root."""
    return path.relative_to(language).with_suffix('').name


def colab_url(github_repo: str, branch: str, path: Path) -> str:
    """Return a Colab URL for the given notebook path."""
    rel_path = path.as_posix()
    return f'https://colab.research.google.com/github/{github_repo}/blob/{branch}/{rel_path}'


def collect_notebooks(root: Path, language: str) -> list[Path]:
    """Collect all notebooks in the given language tree, sorted naturally."""
    language_root = root / language
    visible_files = git_visible_files(root, language)
    notebooks = []

    if visible_files is not None:
        paths = visible_files
    else:
        paths = language_root.rglob('*.ipynb')

    for path in paths:
        if path.suffix != '.ipynb':
            continue
        if path.name == 'README.ipynb':
            continue
        if visible_files is not None:
            notebooks.append(path)
        else:
            notebooks.append(path.relative_to(root))

    return sorted(notebooks, key=natural_key)


def chapter_title(path: Path, language: str) -> str:
    """Return the chapter title for the notebook based on its path relative to the
    language root.
    """
    rel_path = path.relative_to(language)
    if len(rel_path.parts) < 2:
        return 'Notebooks'
    return rel_path.parts[0]


def generate_readme(
    language: str,
    notebooks: list[Path],
    github_repo: str,
    branch: str,
) -> str:
    """Generate the README.md content for the given language tree."""
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


def main():
    """Generate README.md files for each language tree."""
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

        readme = generate_readme(language, notebooks, github_repo, branch)

        file = ROOT / language / 'README.md'
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(readme, encoding='utf-8')


if __name__ == '__main__':
    main()
