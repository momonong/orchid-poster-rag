import io
import json
import tarfile

import pytest

from scripts.build_deployment_bundle import create_archive, safe_name, verify_archive


@pytest.mark.parametrize('value', ['../x', '/x', 'a/../x', 'C:/x', 'a\\x', './x', 'a//x', ''])
def test_bundle_rejects_unsafe_names(value):
    with pytest.raises(ValueError):
        safe_name(value)


def test_bundle_round_trip_hashes_and_excludes_unlisted_files(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'asset').write_bytes(b'approved')
    (root / 'visitor-records.sqlite3').write_bytes(b'private')
    bundle = tmp_path / 'runtime.tar'
    create_archive(root, bundle, {'assets/one': root / 'asset'}, {'source_commit': 'fixture'})
    manifest = verify_archive(bundle)
    assert list(manifest['files']) == ['assets/one']
    target = tmp_path / 'unpacked'
    verify_archive(bundle, target)
    assert (target / 'assets/one').read_bytes() == b'approved'
    assert not (target / 'visitor-records.sqlite3').exists()
    with pytest.raises(FileExistsError):
        verify_archive(bundle, target)
    with tarfile.open(bundle, 'a') as stream:
        member = tarfile.TarInfo('unexpected')
        member.size = 1
        stream.addfile(member, io.BytesIO(b'x'))
    with pytest.raises(ValueError):
        verify_archive(bundle)


def test_bundle_rejects_links_and_hash_tampering_before_extract(tmp_path):
    bundle = tmp_path / 'unsafe.tar'
    with tarfile.open(bundle, 'w') as stream:
        member = tarfile.TarInfo('bundle-manifest.json')
        payload = json.dumps({'files': {'asset': {'size': 1, 'sha256': 'bad'}}}).encode()
        member.size = len(payload)
        stream.addfile(member, io.BytesIO(payload))
        member = tarfile.TarInfo('asset')
        member.size = 1
        stream.addfile(member, io.BytesIO(b'x'))
    target = tmp_path / 'output'
    with pytest.raises(ValueError):
        verify_archive(bundle, target)
    assert not target.exists()
    with tarfile.open(bundle, 'w') as stream:
        member = tarfile.TarInfo('link')
        member.type = tarfile.SYMTYPE
        member.linkname = '/etc/passwd'
        stream.addfile(member)
    with pytest.raises(ValueError):
        verify_archive(bundle, target)
