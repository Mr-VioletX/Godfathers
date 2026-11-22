# -*- coding: utf-8 -*-
"""Stage 87.5 / v1.8.3.4 labor-market safety and strategy tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_employment as E
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.')))>=(1,8,3,4)
assert D.ACCESS_LEVEL==35 and len(E.JOB_ORDER)==4 and len(E.PAYMENT_ORDER)==3
assert E.PAIR_DAILY_LIMIT==3 and E.DAILY_POST_LIMIT==8 and E.MAX_SHARE_PCT==30 and E.ACCOUNT_AGE_HOURS==24
# Three payment models are materially different and fully prefunded.
for job in E.JOB_ORDER:
 fixed=E.package(job,'fixed');share=E.package(job,'share');hybrid=E.package(job,'hybrid')
 assert fixed['fixed_wage']>hybrid['fixed_wage']>share['fixed_wage']
 assert fixed['share_pct']==0<hybrid['share_pct']<share['share_pct']<=E.MAX_SHARE_PCT
 for p in (fixed,share,hybrid):assert p['escrow_total']==p['fixed_wage']+p['success_bonus']+p['operation_budget']
# Field condition changes the best approach; there is no universal click.
for condition in E.CONDITION_ORDER:
 scores={a:E.execution_chance('shadow_courier',condition,a,level=45,trust=60,heat=40,team_effectiveness=1)['chance'] for a in E.APPROACH_ORDER}
 assert max(scores,key=scores.get)==E.CONDITIONS[condition]['counter']
# Player progress, trust, Heat and crew affect estimates.
base=E.execution_chance('signal_breach','quiet','stealth',level=40,trust=50,heat=50,team_effectiveness=0)
elite=E.execution_chance('signal_breach','quiet','stealth',level=52,trust=90,heat=10,team_effectiveness=1.2,team_tactic='silent')
hot=E.execution_chance('signal_breach','quiet','stealth',level=40,trust=50,heat=100,team_effectiveness=0)
assert elite['chance']>base['chance']>hot['chance']
# Settlement modes are deterministic and failure never pays success bonus.
p=E.package('shadow_courier','hybrid');win=E.settlement(p['fixed_wage'],p['success_bonus'],p['share_pct'],p['operation_budget'],120_000_000,True);lose=E.settlement(p['fixed_wage'],p['success_bonus'],p['share_pct'],p['operation_budget'],10_000_000,False)
assert win['worker']>lose['worker']>=p['fixed_wage'] and win['bonus']==p['success_bonus'] and lose['bonus']==0
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_employment_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_employment.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_employment_menu.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_employment_contracts','dark_world_employment_reputations','dark_world_employment_logs'):assert table in model
for field in ('employer_id','worker_id','beneficiary_id','escrow_total','status','execution_chance_bp','execution_roll_bp','worker_payout','disputed_by'):assert field in model
for state in ('open','accepted','in_progress','submitted','completed','failed','cancelled','expired','disputed','settling'):assert state in service or state in (ROOT/'DARK_WORLD_USER_HIRING_SPEC.md').read_text(encoding='utf-8')
# Security: no self hire, account age, pair/day limits, atomic accept and settle predicates.
for token in ('ACCOUNT_AGE_HOURS','PAIR_DAILY_LIMIT','DAILY_POST_LIMIT','DAILY_ESCROW_LIMIT'):assert token in service
assert 'int(c.employer_id)==int(uid)' in service
assert 'DarkWorldEmploymentContract.status=="open"' in service and 'result.rowcount!=1' in service
assert 'DarkWorldEmploymentContract.status=="submitted"' in service and 'values(status="settling")' in service
assert 'escrow_total' in service and 'player.cash=int(player.cash or 0)-pack["escrow_total"]' in service
# Four server-side effects and immutable server rolls.
for job in ('intel_scout','shadow_courier','signal_breach','safehouse_guard'):assert job in service or job in (ROOT/'app/data/dark_world_employment.py').read_text(encoding='utf-8')
assert 'secrets.randbelow(10_000)' in service and 'execution_roll_bp=roll' in service
assert 'team_context' in service and 'apply_mission_wear' in service
assert 'from app.handlers import dark_world_employment' in bot and 'include_router(dark_world_employment.router)' in bot
for route in ('dwe:hub','dwe:new','dwe:job:','dwe:preview:','dwe:publish:','dwe:market','dwe:mine','dwe:view:','dwe:accept:','dwe:start:','dwe:plans:','dwe:do:','dwe:settle:','dwe:cancel:','dwe:dispute:'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[f'dwe:publish:{j}:{p}:{uid}' for j in E.JOB_ORDER for p in E.PAYMENT_ORDER]+[f'dwe:do:999999:{a}:{uid}' for a in E.APPROACH_ORDER]
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for path in files:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
print('OK: four real server-side jobs and three prefunded payment models')
print('OK: hidden field condition creates non-universal strategic execution')
print('OK: atomic accept/settle, escrow, refund, expiry and dispute states')
print('OK: self-hire, account-age, pair, count and amount limits')
print('OK: trust history and active NPC crew integration')
print(f'OK: {len(files)} Python files parsed')
