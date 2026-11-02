"""Bounded offline Linux CPU smoke; writes synthetic data only under /tmp."""
import asyncio
import json
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import torch
from tokenizers import Tokenizer

from orchid.app import create_app
from orchid.config import Settings
from orchid.corpus import verify_sources
from orchid.records import export_records
from orchid.retrieval import HybridIndex
from orchid.speech import SpeechService, validate_wav


class OfflineModel:
    info, reason, quarantined = None, 'offline deployment smoke; no GPU calls', False

    async def probe(self):
        return False

    async def close(self):
        pass


async def main():
    started = time.monotonic()
    assert torch.version.cuda is None and not torch.cuda.is_available()
    torch.set_num_threads(2)
    settings = Settings()
    assert settings.root == Path("/app"), settings.root
    verify_sources(settings)
    tokenizer = Tokenizer.from_file(str(settings.cache / 'qwen-tokenizer/tokenizer.json'))
    assert tokenizer.encode('Orchid deployment smoke').ids
    index = HybridIndex(settings)
    assert index.ready, index.reason
    assert index.search('What controls orchid spots?', language='en')
    speech = SpeechService(settings)
    assert speech.health()['ready']
    lengths = {}
    for language, text in [('en', 'Orchid patterns.'), ('zh-TW', '蘭花斑點。')]:
        lengths[language] = len(validate_wav(await speech.synthesize(text, language)))
    with tempfile.TemporaryDirectory(prefix='orchid-smoke-') as directory:
        # ORCHID_RECORDS_FILE is supplied by the isolated container at /var/lib/orchid.
        app = create_app(settings, index, OfflineModel(), speech)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, root_path=settings.root_path), base_url=f'http://smoke{settings.root_path}/') as client:
            for path in ('/api/health', '/api/guide', '/api/documents/poster', '/api/documents/paper',
                         '/tour-preview/', '/urls.js', '/assets/tour-preview/manifest.json'):
                response = await client.get(path)
                assert response.status_code == 200, (path, response.status_code)
            feedback = {'submission_id': str(uuid4()), 'language': 'en', 'section': 'overview',
                        'clarity': 'clear', 'comment': 'SYNTHETIC deployment smoke'}
            assert (await client.post('/api/feedback', json=feedback)).status_code == 201
        second = create_app(settings, index, OfflineModel(), speech)
        assert second.state.records.ready()
        destination = Path(directory) / 'export'
        export_records(settings.records_file, destination)
        assert (destination / 'records.sqlite3').is_file()
        assert any('SYNTHETIC deployment smoke' in file.read_text(encoding='utf-8-sig')
                   for file in destination.glob('*.csv'))
    print(json.dumps({'status': 'passed', 'torch': torch.__version__, 'cuda': torch.version.cuda,
                      'chunks': len(index.chunks), 'dimension': int(index.vectors.shape[1]),
                      'speech_wav_bytes': lengths, 'synthetic_records_export': True,
                      'elapsed_seconds': round(time.monotonic() - started, 2)}))


if __name__ == '__main__':
    asyncio.run(main())
