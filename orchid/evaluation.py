import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx


def _idle_ready(state):
    if not isinstance(state, dict):
        return False
    index, model, queue = (state.get(name) for name in ('index', 'model', 'queue'))
    return (state.get('app') == 'ready' and isinstance(index, dict) and index.get('ready') is True
            and isinstance(model, dict) and model.get('ready') is True
            and isinstance(queue, dict) and queue.get('active') == 0 and queue.get('pending') == 0)


async def run_live(cases, client, report, checkpoint, language="zh-TW"):
    """Exercise the product API once per question, saving before and after each attempt."""
    rows = report['results']
    report['state'] = 'running'
    checkpoint()
    try:
        health = await client.get('/api/health')
        health.raise_for_status()
        state = health.json()
    except (httpx.HTTPError, ValueError):
        report.update(state='blocked', stopped_reason='product_health_unavailable')
        checkpoint()
        return
    report['preflight'] = state
    if not _idle_ready(state):
        report.update(state='blocked', stopped_reason='product_index_model_not_ready_or_busy')
        checkpoint()
        return

    for case in cases:
        row = {'id': case['id'], 'question': case['question'], 'answerable': case['answerable'],
               'status': 'in_progress', 'requires_human_review': True, 'language': language}
        rows.append(row)
        checkpoint()
        start = time.monotonic()
        try:
            response = await client.post('/api/chat', json={'question': case['question'],
                                                          'history': case.get('history', []), 'language': language})
            row['http_status'] = response.status_code
            response.raise_for_status()
            product = response.json()
            if (not isinstance(product, dict) or product.get('status') not in {
                    'answered', 'unknown', 'busy', 'unavailable'} or not isinstance(product.get('answer'), str)):
                raise ValueError('invalid product response')
            text = product['answer']
            row.update(status=product['status'], answer=text, product_response=product,
                       literal_key_points={point: point.lower() in text.lower() for point in case['key_points']},
                       forbidden_found=[term for term in case['forbidden'] if term in text])
        except asyncio.CancelledError:
            row.update(status='unknown', error='evaluation_cancelled_result_unknown')
            report.update(state='stopped', stopped_reason=row['error'])
            checkpoint()
            raise
        except (httpx.HTTPError, ValueError):
            row.update(status='unknown', error='transport_result_unknown')
            report.update(state='stopped', stopped_reason=row['error'])
        finally:
            row['seconds'] = round(time.monotonic() - start, 3)
            checkpoint()
        if report['state'] == 'stopped':
            return
        if row['status'] in {'busy', 'unavailable'}:
            report.update(state='stopped', stopped_reason='product_busy_or_unavailable')
            checkpoint()
            return
        if row['status'] == 'unknown':
            # Reconcile an unknown once; it may be evidence abstention or unfinished inference.
            try:
                health = await client.get('/api/health')
                health.raise_for_status()
                idle = _idle_ready(health.json())
            except (httpx.HTTPError, ValueError):
                idle = False
            if not idle:
                report.update(state='stopped', stopped_reason='unknown_result_service_not_confirmed_idle')
                checkpoint()
                return
    report['state'] = 'complete'
    checkpoint()


def evaluate(settings, mode, limit, language="zh-TW"):
    if limit < 1:
        raise ValueError('limit 必須大於 0')
    if language not in {"en", "zh-TW"}:
        raise ValueError('unsupported language')
    cases = json.loads((settings.data / 'golden.json').read_text(encoding='utf-8'))[:limit]
    output = settings.root / 'output'
    output.mkdir(exist_ok=True)
    rows = []
    report = {'mode': mode, 'language': language, 'fixture': False, 'cases': 0, 'requested_cases': len(cases),
              'quality_acceptance': '未做人工語意驗收；檢索命中或字面匹配不等於回答正確', 'results': rows}
    latest = output / f'evaluation-{mode}.json'

    if mode == 'live':
        base = os.getenv('ORCHID_APP_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
        parsed = urlparse(base)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('live eval 只接受本機 loopback app origin')
        run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        path = output / f'evaluation-live-{run_id}.json'
        report.update(app_url=base, validation_path='product_api', run_id=run_id)

        def checkpoint():
            report['cases'] = len(rows)
            report['completed_cases'] = sum('product_response' in row for row in rows)
            text = json.dumps(report, ensure_ascii=False, indent=2)
            for target in (path, latest):
                temporary = target.with_suffix('.json.tmp')
                temporary.write_text(text, encoding='utf-8')
                os.replace(temporary, target)

        async def live():
            async with httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(52, connect=3),
                                         trust_env=False, follow_redirects=False) as client:
                await run_live(cases, client, report, checkpoint, language)
        asyncio.run(live())
    else:
        from .retrieval import HybridIndex
        index = HybridIndex(settings)
        if not index.ready:
            raise RuntimeError(index.reason)
        for case in cases:
            start = time.monotonic()
            ids = [p['id'] for p in index.search(case['question'], case.get('history', []), language=language)]
            rows.append({'id': case['id'], 'answerable': case['answerable'], 'retrieved': ids,
                         'retrieval_hit': bool({i.split('_')[0] for i in ids} & set(case['source_any']))
                         if case['answerable'] else None, 'seconds': round(time.monotonic() - start, 3)})
        answerable = [row for row in rows if row['answerable']]
        report.update(cases=len(rows), state='complete', retrieval_hit_rate=
                      sum(row['retrieval_hit'] for row in answerable) / len(answerable) if answerable else None)
        path = latest
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'results', 'preflight'}}, ensure_ascii=False, indent=2))
    print(path.resolve())
    if report.get('state') != 'complete':
        raise RuntimeError('live 評估已停止，已保存逐題 checkpoint；沒有自動重送')
