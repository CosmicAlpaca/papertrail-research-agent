import json
import httpx
from server import llm

def test_quota_fallback_is_used_and_primary_cools_down(monkeypatch):
    monkeypatch.setattr(llm.settings, 'llm_api_key', 'unit-test-placeholder')
    monkeypatch.setattr(llm.settings, 'llm_model', 'primary')
    monkeypatch.setattr(llm.settings, 'llm_fallback_model', 'fallback')
    monkeypatch.setattr(llm, '_cooldowns', {})
    calls = []
    def handle(request):
        model = json.loads(request.content)['model']; calls.append(model)
        if model == 'primary': return httpx.Response(429, json={'error': 'quota'})
        return httpx.Response(200, json={'choices':[{'message':{'content':'{"ok":true}'}}]})
    real_client = httpx.Client
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kwargs: real_client(transport=httpx.MockTransport(handle)))
    first = llm.json_completion('test', {})
    second = llm.json_completion('test', {})
    assert first['_model'] == 'fallback' and first['_attempts'] == 2
    assert second['_attempts'] == 1
    assert calls == ['primary', 'fallback', 'fallback']
