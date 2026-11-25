"""Run the frozen 8-query pilot against a running PaperTrail API.

Usage: python -m evaluation.run_pilot --base http://127.0.0.1:8010
Real API/inference calls incur provider usage. Never embeds or prints credentials.
"""
import argparse
import json
import time
from pathlib import Path
import httpx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8010')
    args = parser.parse_args()
    root = Path(__file__).parent
    tasks = json.loads((root / 'litsearch-pilot-tasks.json').read_text(encoding='utf8'))['tasks']
    output = root / 'results'; output.mkdir(exist_ok=True)
    with httpx.Client(base_url=args.base, timeout=150) as client:
        workspace = client.post('/api/workspaces', json={}); workspace.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + workspace.json()['token']
        for task in tasks:
            path = output / (task['id'] + '.json')
            if path.exists():
                print(task['id'], 'already saved', flush=True); continue
            started = time.monotonic()
            response = client.post('/api/plan', json={'question': task['question']}); response.raise_for_status()
            plan = response.json()
            response = client.post('/api/runs', json={'plan': plan, 'rerank': True, 'repair': True}); response.raise_for_status()
            run_id = response.json()['id']
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                response = client.get('/api/runs/' + run_id); response.raise_for_status()
                row = response.json()
                if row['status'] in {'complete', 'failed'}: break
                time.sleep(2)
            else: raise TimeoutError(task['id'])
            # Remove private capability/workspace data. Preserve genuine results.
            row['task'] = task
            row['end_to_end_seconds'] = round(time.monotonic() - started, 2)
            path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf8')
            print(task['id'], row['status'], row['end_to_end_seconds'], flush=True)

if __name__ == '__main__': main()
