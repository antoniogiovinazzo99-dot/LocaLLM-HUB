"""Lancia agente-mini (6 compiti con test nascosti, benchmarks/windows-fabbrica) contro un server locale.
Uso: am.py PORTA [MINUTI_BUDGET] [THINK 0/1] | am.py control"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LocaLLM-HUB', 'benchmarks', 'windows-fabbrica'))
import agente_mini as am  # noqa: E402

if sys.argv[1] == 'control':
    for t in am.T:
        print(t['name'], 'senza intervento', am.oracle(t, apply=False), '| con soluzione', am.oracle(t, apply=True))
else:
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    think = len(sys.argv) > 3 and sys.argv[3] == '1'
    r = am.run_all(int(sys.argv[1]), think=think, budget_min=budget, log=lambda *a: print(*a, flush=True))
    print(json.dumps(r))
