# -*- coding: utf-8 -*-
"""Stage 87.4 / v1.8.3.3 strategic NPC crew tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world as D
from app.data import dark_world_npcs as N
from app.data import dark_world_cases as C
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,3)
assert D.ACCESS_LEVEL==35 and D.RECRUIT_ORDER==N.NPC_ORDER and len(N.NPC_ORDER)==8
assert N.TEAM_SIZE==3 and N.MAX_LEVEL==10 and len({N.NPCS[k]['class'] for k in N.NPC_ORDER})>=6
# Level, loyalty and fatigue genuinely alter performance.
assert N.member_score(8,90,10)>N.member_score(1,90,10)>N.member_score(1,40,80)>0
# Diversity and medic make team-building a trade-off rather than a fixed best list.
mono=[{'key':'hacker','level':3,'loyalty':80,'fatigue':20,'available':True},{'key':'accountant','level':3,'loyalty':80,'fatigue':20,'available':True}]
diverse=mono+[{'key':'medic','level':3,'loyalty':80,'fatigue':20,'available':True}]
a=N.team_analysis(mono,'balanced');b=N.team_analysis(diverse,'balanced')
assert b['diversity_bonus']>a['diversity_bonus'] and b['medic'] and b['fatigue_mult']<a['fatigue_mult']
# Tactics have different systemic costs/rewards.
team=[{'key':'informant','level':4,'loyalty':85,'fatigue':15,'available':True},{'key':'driver','level':4,'loyalty':85,'fatigue':15,'available':True},{'key':'accountant','level':4,'loyalty':85,'fatigue':15,'available':True}]
silent=N.team_analysis(team,'silent');balanced=N.team_analysis(team,'balanced');aggressive=N.team_analysis(team,'aggressive')
assert silent['heat_mult']<balanced['heat_mult']<aggressive['heat_mult']
assert silent['cash_mult']<balanced['cash_mult']<aggressive['cash_mult']
assert silent['chance_bonus']>balanced['chance_bonus']>aggressive['chance_bonus']
assert N.skill_bonus(team,'stealth','silent')>N.skill_bonus(team,'stealth','balanced')
# Payroll and betrayal create management pressure.
assert N.salary('hacker',5)>N.salary('hacker',1)>0 and N.training_cost('ghost',5)>N.training_cost('ghost',1)
assert N.betrayal_chance(20,2,.1)>N.betrayal_chance(90,0,.1)==0
# Team tactic and effectiveness flow into both operation engines.
base=D.contract_plan('night_route','calculated',team_effectiveness=1,team_tactic='balanced')
quiet=D.contract_plan('night_route','calculated',team_effectiveness=1,team_tactic='silent')
loud=D.contract_plan('night_route','calculated',team_effectiveness=1,team_tactic='aggressive')
assert quiet['heat_success']<base['heat_success']<loud['heat_success'] and quiet['cash_success']<base['cash_success']<loud['cash_success']
choice=C.get_choice('midnight_train','platform','roof')
assert C.choice_chance(choice,40,100,0,0,0,('informant',),None,1,'silent')['chance']>C.choice_chance(choice,40,100,0,0,0,('informant',),None,1,'balanced')['chance']
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_npc_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_npcs.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_npc_menu.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_recruit_states','dark_world_teams','dark_world_recruit_events'):assert table in model
for field in ('fatigue','wage_due_at','training_until','rest_until','injured_until','deserted','member_keys_json','tactic_key'):assert field in model
for mechanic in ('apply_mission_wear','betrayal_chance','injured_until','unpaid_cycles','TEAM_SIZE'):assert mechanic in service or mechanic in (ROOT/'app/data/dark_world_npcs.py').read_text(encoding='utf-8')
assert 'from app.handlers import dark_world_npcs' in bot and 'include_router(dark_world_npcs.router)' in bot
for route in ('dwn:hub','dwn:team','dwn:tactics','dwn:toggle:','dwn:tactic:','dwn:train:','dwn:wages','dwn:rest','dwn:return:'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
# Integration points: only active effective crew is used by contracts, cases and pursuit.
for f in ('app/services/dark_world_service.py','app/services/dark_world_case_service.py','app/services/dark_world_pursuit_service.py'):
 s=(ROOT/f).read_text(encoding='utf-8');assert 'team_context' in s
assert 'apply_mission_wear' in (ROOT/'app/services/dark_world_service.py').read_text(encoding='utf-8')
assert 'apply_mission_wear' in (ROOT/'app/services/dark_world_case_service.py').read_text(encoding='utf-8')
uid='1234567890123456789';callbacks=[f'dwn:toggle:{k}:{uid}' for k in N.NPC_ORDER]+[f'dwn:train:{k}:{uid}' for k in N.NPC_ORDER]+[f'dwn:tactic:{k}:{uid}' for k in N.TACTIC_ORDER]
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: eight NPCs across six classes and a three-member active crew')
print('OK: level, loyalty, fatigue, injury, payroll, training and desertion')
print('OK: class diversity, medic support and three asymmetric tactics')
print('OK: active crew affects timed contracts, branching cases and pursuit')
print('OK: restart-safe tables, guarded mutations and callback limits')
print(f'OK: {len(files)} Python files parsed')
