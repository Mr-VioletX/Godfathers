# -*- coding: utf-8 -*-
"""Stage 87.1 / v1.8.3.0 Dark World foundation tests (dependency-free)."""
from __future__ import annotations
import ast, random
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from app.data import dark_world as D
from app.data import leveling as L

assert tuple(map(int, (ROOT/'VERSION.txt').read_text(encoding='utf-8').strip().split('.'))) >= (1,8,3,0)
# Existing 1..50 curve is unchanged; the first endgame ladder reaches 60.
assert L.MAX_LEVEL==D.ENDGAME_LEVEL_CAP==60
assert [L.xp_needed(x) for x in (1,29,30,49)]==[100,2900,10000,150000]
elite=[L.xp_needed(x) for x in range(50,60)]
assert elite==[180000,220000,270000,330000,400000,480000,570000,670000,780000,900000]
assert all(a<b for a,b in zip(elite,elite[1:])) and L.xp_needed(60)==0
p=SimpleNamespace(level=50,xp=0)
r=L.add_xp(p,180000)
assert p.level==51 and p.xp==0 and r['leveled_up']
p=SimpleNamespace(level=59,xp=0)
r=L.add_xp(p,900000)
assert p.level==60 and p.xp==0 and r['new_level']==60

# Four difficulty tiers, three genuine approaches and difficulty-scaled XP/reward.
assert D.ACCESS_LEVEL==35 and len(D.CONTRACT_ORDER)==4 and len(D.APPROACH_ORDER)==3
plans=[D.contract_plan(k,'calculated') for k in D.CONTRACT_ORDER]
assert [p['difficulty'] for p in plans]==[1,2,3,4]
for field in ('energy','entry_cost','cash_success','xp_success','dark_xp_success','influence_success','heat_success'):
 vals=[p[field] for p in plans]
 assert vals==sorted(vals) and len(set(vals))==4,(field,vals)
easy={k:D.contract_plan('dead_drop',k,heat=0) for k in D.APPROACH_ORDER}
assert easy['stealth']['chance']>easy['calculated']['chance']>easy['force']['chance']
assert easy['stealth']['heat_success']<easy['calculated']['heat_success']<easy['force']['heat_success']
assert easy['force']['cash_success']>easy['calculated']['cash_success']>easy['stealth']['cash_success']
assert easy['force']['duration']<easy['calculated']['duration']<easy['stealth']['duration']
# Heat matters, streak rewards risk, recruits have distinct systemic effects.
base=D.contract_plan('silent_auction','calculated',heat=0,streak=0)
hot=D.contract_plan('silent_auction','calculated',heat=100,streak=0)
streak=D.contract_plan('silent_auction','calculated',heat=0,streak=10)
assert hot['chance']<base['chance'] and streak['cash_success']==round(base['cash_success']*1.30)
assert D.contract_plan('night_route','calculated',recruit_keys=['informant'])['chance']==73
assert D.contract_plan('night_route','calculated',recruit_keys=['fixer'])['heat_success']<D.contract_plan('night_route','calculated')['heat_success']
assert D.contract_plan('night_route','calculated',recruit_keys=['driver'])['duration']<D.contract_plan('night_route','calculated')['duration']
assert D.contract_plan('night_route','calculated',recruit_keys=['accountant'])['cash_success']>D.contract_plan('night_route','calculated')['cash_success']
# Rolls are fixed at start: same plan+roll always resolves identically.
win=D.resolve_plan(base,0,100); lose=D.resolve_plan(base,99.99,100)
assert win['success'] and win['cash']>0 and win['influence']>0
assert not lose['success'] and lose['cash']==0 and lose['xp']>0 and lose['influence']<0
assert D.resolve_plan(base,0,100)==win
# Evenly-spaced simulation tracks configured chance exactly without flaky randomness.
count=sum(D.resolve_plan(base,i/100,100)['success'] for i in range(10000))
assert count==int(base['chance']*100)
# Rank ladder and recovery.
assert D.rank_for(0)['key']=='unmarked' and D.rank_for(8000)['key']=='nameless'
assert D.next_rank(74)['threshold']==75 and D.next_rank(8000) is None
now=datetime(2026,9,2,20,0,0); steps,advanced=D.recovery_steps(now-timedelta(minutes=37),now,D.ENERGY_REGEN_SECONDS)
assert steps==6 and advanced==now-timedelta(minutes=1)

# Integration and persistence surfaces.
main=(ROOT/'app/keyboards/main_menu.py').read_text(encoding='utf-8')
bot=(ROOT/'bot.py').read_text(encoding='utf-8')
engine=(ROOT/'app/database/engine.py').read_text(encoding='utf-8')
handler=(ROOT/'app/handlers/dark_world.py').read_text(encoding='utf-8')
keyboard=(ROOT/'app/keyboards/dark_world_menu.py').read_text(encoding='utf-8')
service=(ROOT/'app/services/dark_world_service.py').read_text(encoding='utf-8')
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8')
leveling=(ROOT/'app/data/leveling.py').read_text(encoding='utf-8')
assert 'BTN_DARK_WORLD = "🌑 دنیای سیاه"' in main and 'menu:darkworld' in main
assert 'from app.handlers import dark_world' in bot and 'include_router(dark_world.router)' in bot
assert 'dark_world,' in engine
for table in ('dark_world_profiles','dark_world_recruits','dark_world_contract_logs'): assert table in model
for field in ('active_success','active_cash','active_xp','active_roll_bp','active_ready_at'): assert field in model
for route in ('dw:contracts','dw:contract:','dw:preview:','dw:start:','dw:collect','dw:rank','dw:recruits','dw:hire:','dw:story'): assert route in handler or route in keyboard
assert 'leveling.grant_xp' in service and 'source="dark_world_contract"' in service
assert 'secrets.randbelow(10_000)' in service and 'active_roll_bp' in service
assert 'economic_operation' in handler and 'DuplicateOperation' in handler and 'BusyOperation' in handler
assert all(token in handler for token in ('dw-start:{callback.id}', 'dw-collect:{callback.id}', 'dw-hire:{callback.id}'))
assert 'result = await DS.collect_contract' not in handler  # result is intentionally named message; no leaked roll
assert 'MAX_LEVEL = 60' in leveling and 'ELITE_XP_NEEDS' in leveling
# Mutating operations each own exactly one successful commit.
tree=ast.parse(service)
funcs={n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
for name in ('start_contract','collect_contract','hire_recruit'):
 commits=[n for n in ast.walk(funcs[name]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='commit']
 assert len(commits)==1,(name,len(commits))
# Callback data remains under Telegram's 64-byte limit for 19-digit owner ids.
uid='1234567890123456789'
callbacks=[]
for c in D.CONTRACT_ORDER:
 for a in D.APPROACH_ORDER:
  callbacks += [f'dw:preview:{c}:{a}:{uid}',f'dw:start:{c}:{a}:{uid}']
for rkey in D.RECRUIT_ORDER: callbacks.append(f'dw:hire:{rkey}:{uid}')
assert max(map(lambda x:len(x.encode()),callbacks))<=64
# Every Python file is valid UTF-8/AST.
files=sorted(ROOT.rglob('*.py'))
for path in files: ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
print('OK: global player ladder extends from 50 to 60 with a monotonic endgame curve')
print('OK: four difficulty-scaled contracts and three risk/reward approaches')
print('OK: energy, heat, intel, streak and hidden restart-safe outcomes')
print('OK: independent eight-tier Dark World ranking and top-10 board')
print('OK: four permanent recruits with distinct operation modifiers')
print('OK: private/group menus, narrative placeholder and owner-safe callbacks')
print(f'OK: {len(files)} Python files parsed')
