"""Scout: cerca su Hugging Face modelli GGUF nuovi e plausibili per la 3060 e li accoda (automatico, senza token)."""
import json, pathlib, re, urllib.request

ROOT = pathlib.Path(r'<HOME>\llm\fabbrica')
LLAMA_DLL = r'<HOME>\llm\bin-b10955\llama.dll'
ALLOW = {'qwen35', 'qwen35moe', 'qwen3', 'qwen3moe', 'qwen3next', 'gemma4', 'gpt-oss', 'laguna', 'lfm2moe', 'lfm3', 'glm4moe', 'spark2_5', 'granitehybrid', 'exaone-moe', 'hunyuan-moe', 'ernie4_5-moe', 'bailingmoe2', 'llama', 'phi3', 'granite', 'olmo2', 'olmoe'}
SKIP_NAME = re.compile(r'abliterat|uncensor|heretic|obliterat|aggressive|jailbreak|nsfw|rp-|roleplay|tts|asr|embed|rerank|music|image|vision-only|mmproj', re.I)
BASE = 'https://huggingface.co/api/models?filter=gguf&limit=100&expand[]=gguf&expand[]=downloads&expand[]=createdAt'


def hf(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'fabbrica'}), timeout=60))


def refill(max_new=6, min_downloads=40000, since='2026-07-15'):
    sup = set(x.decode() for x in re.findall(rb'[a-z][a-z0-9_.-]{2,24}', open(LLAMA_DLL, 'rb').read()))
    queue = json.loads((ROOT / 'coda.json').read_text(encoding='utf-8'))
    known = {q.get('repo') for q in queue}
    seen = {}
    for sort in ('trendingScore', 'downloads', 'createdAt'):
        try:
            for m in hf(BASE + f'&sort={sort}&direction=-1'):
                seen[m['id']] = m
        except Exception:
            pass
    groups = {}
    for i, m in seen.items():
        g = m.get('gguf') or {}
        arch, tot = g.get('architecture'), g.get('total') or 0
        if i in known or arch not in ALLOW or not (arch in sup or arch.replace('_', '-') in sup):
            continue
        if SKIP_NAME.search(i) or not (3e9 <= tot <= 46e9) or (m.get('createdAt') or '')[:10] < since or (m.get('downloads') or 0) < min_downloads:
            continue
        groups.setdefault((arch, round(tot / 1e9)), []).append(m)
    cand = []
    for k, v in groups.items():
        v.sort(key=lambda m: -(m.get('downloads') or 0))
        cand += v[:1]
    cand.sort(key=lambda m: -(m.get('downloads') or 0))
    added = 0
    for m in cand[:max_new]:
        name = re.sub(r'[^a-z0-9.]+', '-', m['id'].split('/')[-1].lower().replace('-gguf', ''))[:40]
        queue.append({'name': name, 'repo': m['id'], 'cap': 24, 'auto': True})
        added += 1
    if added:
        (ROOT / 'coda.json').write_text(json.dumps(queue, indent=1), encoding='utf-8')
    return added
