import asyncio
import io
import json
import threading
import wave

import httpx
import pytest

from orchid.config import Settings


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(b'\x01\x00' * 2400)
    return output.getvalue()


def test_narration_keeps_conditions_and_spells_identifiers_without_citations():
    from orchid.speech import narration_text
    source = '**PeMYB11** and PeMYBx, HORT1, miR858; G_A = 0.01, µ_A = 0.02; D_H > D_A [P01].'
    text = narration_text(source, 'en')
    for expected in ('P E M Y B one one', 'P E M Y B X', 'H O R T one', 'M I R eight five eight',
                     'G A equals zero point zero one', 'mu A equals zero point zero two', 'D H greater than D A'):
        assert expected in text
    assert '[P01]' not in text and '**' not in text
    assert source.startswith('**PeMYB11**')  # Narration does not mutate displayed source.
    chinese = narration_text('蘭花中 PeMYB11；D_H > D_A，不能單獨保證斑點融合。', 'zh-TW')
    assert 'P E M Y B 一 一' in chinese and 'D H 大于 D A' in chinese
    assert '不能单独保证' in chinese  # Model phonemization only; displayed text stays Traditional Chinese.
    assert 'D A less than D H' in narration_text('D_A < D_H and D_H > D_A', 'en')


def test_english_parameters_cannot_enter_chinese_number_normalizer():
    from orchid.speech import narration_text
    text = narration_text('G_A_whi = 0.0296; 100 × 100; µ_H = 0.03; ρ_A = 0.01; D_H > D_A; 2 µM.', 'en')
    assert 'G A W H I equals zero point zero two nine six' in text
    assert 'one zero zero times one zero zero' in text
    assert 'mu H equals zero point zero three' in text
    assert 'rho A equals zero point zero one' in text
    assert 'two micromolar' in text
    assert not any(char.isdigit() for char in text)


@pytest.mark.asyncio
async def test_api_returns_bounded_wav_and_uses_server_guide_text(tmp_path):
    from orchid.app import create_app
    from orchid.speech import SpeechService
    calls = []

    def render(text, language, cancelled):
        calls.append((text, language))
        return wav_bytes()

    data = tmp_path / 'data'
    data.mkdir()
    (data / 'guide.en.json').write_text(json.dumps({'introduction': 'Vetted introduction.',
                                                 'clues': []}), encoding='utf-8')
    service = SpeechService(Settings(root=tmp_path), renderer=render)
    app = create_app(Settings(root=tmp_path), speech=service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/speech', json={'guide_id': 'intro', 'text': 'untrusted replacement'})
        assert response.status_code == 200 and response.content == wav_bytes()
        assert response.headers['content-type'].startswith('audio/wav')
        assert response.headers['cache-control'] == 'no-store'
        assert "media-src 'self' blob:" in response.headers['content-security-policy']
        assert calls == [('Vetted introduction.', 'en')]
        assert (await client.post('/api/speech', json={'text': 'x' * 4001})).status_code == 422
        assert (await client.post('/api/speech', json={'text': 'x', 'language': 'zh-CN'})).status_code == 422
        assert (await client.post('/api/speech', json={'text': '   '})).status_code == 422
        assert (await client.post('/api/speech', json={'guide_id': '../secret'})).status_code == 404
        assert (await client.post('/api/speech', json={'text': 'x', 'path': '../secret'})).status_code == 422
        response = await client.post('/api/speech', json={'text': '繁體中文回答 [P01]', 'language': 'zh-TW'})
        assert response.status_code == 200
        assert calls[-1][1] == 'zh-TW' and '[P01]' not in calls[-1][0]


@pytest.mark.asyncio
async def test_answer_cache_expires_and_static_cache_never_stores_answer_text(tmp_path):
    from orchid.speech import SpeechService
    calls = []
    clock = [100.0]

    def render(text, language, cancelled):
        calls.append(text)
        return wav_bytes()

    service = SpeechService(Settings(root=tmp_path), renderer=render, clock=lambda: clock[0], cache_seconds=1)
    await service.synthesize('Private answer [P01]', 'en')
    await service.synthesize('Private answer [P01]', 'en')
    assert len(calls) == 1
    assert not (tmp_path / '.cache' / 'speech').exists()
    clock[0] += 2
    await service.synthesize('Private answer [P01]', 'en')
    assert len(calls) == 2
    await service.synthesize('Vetted static guide.', 'en', guide_id='intro')
    cached = list((tmp_path / '.cache' / 'speech').glob('*.wav'))
    assert len(cached) == 1 and cached[0].read_bytes() == wav_bytes()
    assert 'Private' not in cached[0].name


@pytest.mark.asyncio
async def test_answer_audio_is_evicted_without_another_request(tmp_path):
    from orchid.speech import SpeechService
    service = SpeechService(Settings(root=tmp_path), renderer=lambda *args: wav_bytes(), cache_seconds=0.01)
    await service.synthesize('Private answer.', 'en')
    assert service.answer_cache
    await asyncio.sleep(0.05)
    assert not service.answer_cache


@pytest.mark.asyncio
async def test_api_busy_and_timeout_are_explicit_and_do_not_start_extra_workers(tmp_path):
    from orchid.app import create_app
    from orchid.speech import SpeechService
    entered = threading.Event()
    release = threading.Event()

    def render(text, language, cancelled):
        entered.set()
        release.wait(2)
        return wav_bytes()

    service = SpeechService(Settings(root=tmp_path), renderer=render, response_seconds=0.03)
    app = create_app(Settings(root=tmp_path), speech=service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        first = asyncio.create_task(client.post('/api/speech', json={'text': 'First'}))
        await asyncio.to_thread(entered.wait, 1)
        response = await first
        assert response.status_code == 504 and service.health()['active'] == 1
        # The first call proves timeout behavior. Give the subsequent admission
        # check enough time to traverse real middleware before its waiters expire.
        service.response_seconds = 1
        second = asyncio.create_task(service.synthesize('Second', 'en'))
        third = asyncio.create_task(service.synthesize('Third', 'en'))
        await asyncio.sleep(0)
        response = await client.post('/api/speech', json={'text': 'Fourth'})
        assert response.status_code == 429
        second.cancel()
        third.cancel()
        await asyncio.gather(second, third, return_exceptions=True)
        release.set()
        await asyncio.gather(*service.queue.tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_asgi_disconnect_signals_worker_even_through_body_and_header_middleware(tmp_path):
    from orchid.app import create_app
    from orchid.speech import SpeechService
    entered = threading.Event()
    observed_cancel = threading.Event()
    release = threading.Event()

    def render(text, language, cancelled):
        entered.set()
        for _ in range(150):
            if cancelled.is_set():
                observed_cancel.set()
                break
            if release.wait(0.01):
                break
        return wav_bytes()

    service = SpeechService(Settings(root=tmp_path), renderer=render)
    app = create_app(Settings(root=tmp_path), speech=service)
    messages = asyncio.Queue()
    await messages.put({'type': 'http.request', 'body': b'{"text":"Hello."}', 'more_body': False})
    scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1',
             'method': 'POST', 'scheme': 'http', 'path': '/api/speech', 'raw_path': b'/api/speech',
             'query_string': b'', 'root_path': '', 'headers': [(b'content-type', b'application/json')],
             'client': ('127.0.0.1', 1234), 'server': ('127.0.0.1', 8002)}

    async def send(message):
        pass

    request = asyncio.create_task(app(scope, messages.get, send))
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        await messages.put({'type': 'http.disconnect'})
        assert await asyncio.to_thread(observed_cancel.wait, 0.5), 'ASGI disconnect must reach the CPU cancellation event'
    finally:
        release.set()
        await asyncio.wait_for(request, 2)
        await asyncio.gather(*service.queue.tasks, return_exceptions=True)
    assert service.health()['active'] == 0 and not service.answer_cache


@pytest.mark.asyncio
async def test_timeout_retains_worker_slot_until_real_thread_finishes(tmp_path):
    from orchid.generation import Busy
    from orchid.speech import SpeechService, SpeechTimeout
    entered = threading.Event()
    release = threading.Event()
    cancelled_seen = []

    def render(text, language, cancelled):
        entered.set()
        release.wait(2)
        cancelled_seen.append(cancelled.is_set())
        return wav_bytes()

    service = SpeechService(Settings(root=tmp_path), renderer=render, response_seconds=0.03)
    first = asyncio.create_task(service.synthesize('First', 'en'))
    await asyncio.to_thread(entered.wait, 1)
    with pytest.raises(SpeechTimeout):
        await first
    assert service.health()['active'] == 1
    # Client cancellation cannot free capacity while its CPU worker is still alive.
    second = asyncio.create_task(service.synthesize('Second', 'en'))
    third = asyncio.create_task(service.synthesize('Third', 'en'))
    await asyncio.sleep(0)
    with pytest.raises(Busy):
        await service.synthesize('Fourth', 'en')
    second.cancel()
    third.cancel()
    await asyncio.gather(second, third, return_exceptions=True)
    release.set()
    for _ in range(50):
        if not service.health()['active']:
            break
        await asyncio.sleep(0.01)
    assert service.health()['active'] == 0 and cancelled_seen == [True]
    assert not service.answer_cache


@pytest.mark.asyncio
async def test_audio_failure_and_unprovisioned_models_are_explicit(tmp_path):
    from orchid.app import create_app
    from orchid.speech import SpeechService
    settings = Settings(root=tmp_path)
    unavailable = SpeechService(settings)
    assert unavailable.health()['ready'] is False
    app = create_app(settings, speech=unavailable)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/speech', json={'text': 'Hello'})
        assert response.status_code == 503
        assert str(tmp_path) not in response.text
    broken = SpeechService(settings, renderer=lambda *args: b'not audio')
    app = create_app(settings, speech=broken)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/speech', json={'text': 'Hello'})
        assert response.status_code == 503
