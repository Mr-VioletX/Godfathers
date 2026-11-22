# -*- coding: utf-8 -*-
"""Stage 87.7 / v1.8.3.6 black-finance and fictional roadmap tests."""
from __future__ import annotations
import ast,sys
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_finance as F
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,6)
assert D.ACCESS_LEVEL==35 and len(F.METHOD_ORDER)==3 and F.TRACE_MAX==100
# Laundering methods have genuine fee/time/risk trade-offs.
front=F.plan(200_000_000,'front',trace=20);broker=F.plan(200_000_000,'broker',trace=20);shell=F.plan(200_000_000,'shell',trace=20)
assert front['chance']>broker['chance']>shell['chance']
assert front['fee_pct']>broker['fee_pct']>shell['fee_pct']
assert front['duration']>broker['duration']>shell['duration']
assert front['trace_gain']<broker['trace_gain']<shell['trace_gain']
# Trace and amount matter; rare tools can change the plan without guaranteeing success.
clean=F.plan(50_000_000,'broker',trace=0);hot=F.plan(500_000_000,'broker',trace=90);boost=F.plan(500_000_000,'broker',trace=90,has_key=True,has_pass=True,has_ledger=True)
assert clean['chance']>hot['chance'] and boost['chance']>hot['chance']
assert boost['trace_gain']<hot['trace_gain'] and boost['fee_pct']<hot['fee_pct']
# Outcomes are deterministic for a persisted roll and failed capital is partially confiscated.
win=F.resolve(broker,0);lose=F.resolve(broker,99.99)
assert win['success'] and win['clean']>0 and win['confiscated']==0
assert not lose['success'] and lose['clean']==0 and lose['confiscated']>0 and lose['dirty_refund']+lose['confiscated']==broker['amount']
assert F.resolve(broker,0)==win
# Enforcement climate and rare broker stock rotate by day.
d=date(2026,9,3);assert F.climate(d)['key']!=F.climate(d+timedelta(days=1))['key'];assert F.rare_today(d)!=F.rare_today(d+timedelta(days=1))
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_finance_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_finance.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_finance_menu.py').read_text(encoding='utf-8');smuggling=(ROOT/'app/services/dark_world_smuggling_service.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8');roadmap=(ROOT/'STAGE87_DARK_WORLD_ROADMAP.md').read_text(encoding='utf-8')
for table in ('dark_world_finance','dark_world_laundering_jobs','dark_world_rare_inventory','dark_world_finance_logs'):assert table in model
for field in ('dirty_balance','trace','chance_bp','roll_bp','confiscated','dirty_refund','trace_gain'):assert field in model
assert 'credit_dirty' in smuggling and 'player.cash=int(player.cash or 0)+int(ship.result_cash or 0)' not in smuggling
assert 'secrets.randbelow(10_000)' in service and 'result_success=out["success"]' in service and 'roll_bp=roll' in service
assert 'DarkWorldSmugglingInventory' in service and 'int(a.trace)>=70' in service
assert 'from app.handlers import dark_world_finance' in bot and 'include_router(dark_world_finance.router)' in bot
for route in ('dwf:hub','dwf:amounts','dwf:methods:','dwf:prev:','dwf:start:','dwf:active','dwf:rare','dwf:buy:','dwf:log'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
# Future text-management expansion is fictional and deliberately excludes actionable real-world production instructions.
for stage in ('۸۷.۱۱','۸۷.۱۲','۸۷.۱۳','۸۷.۱۴'):assert stage in roadmap
for phrase in ('کاملاً خیالی','هیچ نام، فرمول، ماده شیمیایی یا روش واقعی','اجزای خیالی A/B/C','هیچ دستور واقعی'):assert phrase in roadmap
assert 'مشتریان، محله‌ها و شبکه توزیع' in roadmap and 'رقبا، بازرسی و امپراتوری تولید' in roadmap
uid='1234567890123456789';callbacks=[f'dwf:start:100:{m}:{uid}' for m in F.METHOD_ORDER]+[f'dwf:buy:{k}:{uid}' for k in F.RARE_ORDER]
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: dirty money, three laundering methods and rotating enforcement climate')
print('OK: persisted hidden outcomes, trace decay, confiscation and rare brokers')
print('OK: smuggling proceeds feed dirty balance instead of clean cash')
print('OK: future fictional text-management product roadmap added safely')
print('OK: guarded owner-bound finance actions and callback limits')
print(f'OK: {len(files)} Python files parsed')
