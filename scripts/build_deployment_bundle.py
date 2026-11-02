"""Allowlisted offline runtime archive. Never reads visitor records or credentials."""

import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path, PurePosixPath

E5_FILES = ('config.json', 'model.safetensors', 'modules.json', 'sentence_bert_config.json',
            'sentencepiece.bpe.model', 'special_tokens_map.json', 'tokenizer.json',
            'tokenizer_config.json', '1_Pooling/config.json', 'README.md')
LEGACY_ASSETS = ('flowers.webp', 'clue1.webp', 'clue2.webp', 'clue3.webp', 'intro.webp',
                 'methods.webp', 'discussion.webp', 'poster.png')
KOKORO = '.cache/tts/kokoro-multi-lang-v1_1'


def safe_name(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or value.startswith('/') or any(part in {'', '.', '..'} for part in value.split('/'))):
        raise ValueError('Unsafe bundle path')
    return PurePosixPath(value)


def secure_file(root, path):
    root, path = root.resolve(), Path(path)
    # Reject symlinks and Windows junction/reparse points, including intermediate directories.
    current = path.absolute()
    while current != root:
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('Links are not allowed in runtime assets')
        if current == current.parent:
            raise ValueError('Runtime path escapes source root')
        current = current.parent
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Runtime file missing or outside source root')
    return path


def digest_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def collect_runtime(root):
    root = Path(root).resolve()
    files = {}

    def add(name, source=None):
        safe_name(name)
        files[name] = secure_file(root, root / (source or name))

    for name in E5_FILES:
        add('.cache/e5-model/' + name)
    for name in ('tokenizer.json', 'provenance.json'):
        add('.cache/qwen-tokenizer/' + name)
    provenance = json.loads(files['.cache/qwen-tokenizer/provenance.json'].read_text(encoding='utf-8'))
    if digest_file(files['.cache/qwen-tokenizer/tokenizer.json']) != provenance['sha256']:
        raise ValueError('Tokenizer receipt mismatch')
    for name in ('chunks.json', 'vectors.npy', 'manifest.json'):
        add('.orchid/index/' + name)
    receipt = json.loads(secure_file(root, root / KOKORO / 'provision.json').read_text(encoding='utf-8'))
    add(KOKORO + '/provision.json')
    for name, digest in receipt['files'].items():
        safe_name(name)
        # Exact provision receipt, not recursive cache copying.
        add(KOKORO + '/' + name)
        if digest_file(files[KOKORO + '/' + name]) != digest:
            raise ValueError('Kokoro receipt mismatch')
    for name in LEGACY_ASSETS:
        add('.orchid/assets/' + name)
    for manifest in ('manifest.json', 'audio/manifest.json'):
        add('.orchid/assets/tour-preview/' + manifest)
    image_manifest = json.loads(files['.orchid/assets/tour-preview/manifest.json'].read_text(encoding='utf-8'))
    audio_manifest = json.loads(files['.orchid/assets/tour-preview/audio/manifest.json'].read_text(encoding='utf-8'))
    urls = [v['url'] for item in image_manifest['images'].values() for v in item['variants']]
    urls += [item['url'] for item in audio_manifest['items']]
    for url in urls:
        if not re.fullmatch(r'/assets/tour-preview/(?:audio/)?[A-Za-z0-9_.-]+\.(?:webp|wav)', url):
            raise ValueError('Unexpected manifest asset URL')
        add('.orchid' + url)
    for language in ('en', 'zh-TW'):
        for kind in ('guide', 'question', 'feedback'):
            add(f'.orchid/assets/tour-preview/help/{language}-{kind}.png')
    sources = json.loads(secure_file(root, root / 'data/sources.json').read_text(encoding='utf-8'))
    for key in ('poster', 'paper'):
        item = sources[key]
        original = safe_name(item['path']).as_posix()
        if Path(original).suffix.lower() != '.pdf' or key not in {'poster', 'paper'}:
            raise ValueError('Unexpected registered PDF')
        target = f'pdfs/{key}.pdf'
        add(target, original)
        if digest_file(files[target]) != item['sha256']:
            raise ValueError('Registered PDF hash mismatch')
        item['path'] = target
    files['data/sources.json'] = json.dumps(sources, ensure_ascii=False, indent=2).encode('utf-8')
    files['.cache/speech/.keep'] = b''
    return files


def create_archive(root, output, files, metadata):
    root, output = Path(root).resolve(), Path(output)
    if output.exists():
        raise FileExistsError(output)
    entries = {}
    for name, source in sorted(files.items()):
        safe_name(name)
        if name == 'bundle-manifest.json':
            raise ValueError('Reserved manifest name')
        if isinstance(source, bytes):
            digest, size = hashlib.sha256(source).hexdigest(), len(source)
        else:
            source = secure_file(root, source)
            digest, size = digest_file(source), source.stat().st_size
        entries[name] = {'sha256': digest, 'size': size}
    manifest = {'schema': 1, 'metadata': metadata, 'files': entries}
    payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    with tarfile.open(output, 'w', format=tarfile.PAX_FORMAT) as archive:
        for name, source in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.mode, member.uid, member.gid, member.mtime = 0o644, 0, 0, 0
            member.size = entries[name]['size']
            if isinstance(source, bytes):
                archive.addfile(member, io.BytesIO(source))
            else:
                with Path(source).open('rb') as stream:
                    archive.addfile(member, stream)
        member = tarfile.TarInfo('bundle-manifest.json')
        member.size, member.mode = len(payload), 0o644
        archive.addfile(member, io.BytesIO(payload))
    # Verify the bytes that were actually archived, including concurrent source changes.
    verify_archive(output)
    return manifest


def verify_archive(archive_path, destination=None):
    destination = Path(destination) if destination is not None else None
    if destination is not None and destination.exists():
        raise FileExistsError(destination)
    with tarfile.open(archive_path, 'r:*') as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive paths')
        for member in members:
            safe_name(member.name)
            if not member.isfile():
                raise ValueError('Only regular files are allowed')
        if names.count('bundle-manifest.json') != 1:
            raise ValueError('Missing bundle manifest')
        info = archive.getmember('bundle-manifest.json')
        if info.size > 2_000_000:
            raise ValueError('Manifest too large')
        manifest = json.load(archive.extractfile(info))
        if manifest.get('schema') != 1:
            raise ValueError('Unsupported bundle schema')
        if set(names) != set(manifest['files']) | {'bundle-manifest.json'}:
            raise ValueError('Unlisted or missing archive file')
        for name, expected in manifest['files'].items():
            safe_name(name)
            member = archive.getmember(name)
            if member.size != expected['size']:
                raise ValueError('Bundle size mismatch')
            with archive.extractfile(member) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected['sha256']:
                    raise ValueError('Bundle hash mismatch')
        if destination is not None:
            destination.mkdir(parents=True)
            # No tar extract() calls: parent dirs and regular files are created explicitly.
            for member in members:
                target = destination.joinpath(*safe_name(member.name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open('xb') as output:
                    import shutil
                    shutil.copyfileobj(source, output)
                target.chmod(0o644)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    build.add_argument('--output', type=Path, required=True)
    build.add_argument('--source-commit', required=True)
    build.add_argument('--image', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('archive', type=Path)
    verify.add_argument('--extract', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        manifest = verify_archive(args.archive, args.extract)
    else:
        from orchid.config import E5_MODEL, E5_REVISION, QWEN_MODEL, QWEN_REVISION
        from orchid.speech import MODEL_SHA256
        manifest = create_archive(args.root, args.output, collect_runtime(args.root), {
            'source_commit': args.source_commit, 'image': args.image,
            'pdf_mapping': {key: {'original': value['path'], 'runtime': f'pdfs/{key}.pdf'}
                            for key, value in json.loads((args.root / 'data/sources.json').read_text(encoding='utf-8')).items()
                            if key in {'poster', 'paper'}},
            'e5': {'model': E5_MODEL, 'revision': E5_REVISION},
            'tokenizer': {'model': QWEN_MODEL, 'revision': QWEN_REVISION},
            'kokoro_archive_sha256': MODEL_SHA256,
            'excluded': ['visitor records', 'credentials', 'logs', 'Qwen model weights']})
    print(json.dumps({'files': len(manifest['files']), 'metadata': manifest.get('metadata', {})}, ensure_ascii=False))


if __name__ == '__main__':
    main()
