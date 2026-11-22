# -*- coding: utf-8 -*-
"""Stage 87.3 / v1.8.3.2 strategic pursuit regression tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world as D
from app.data import dark_world_pursuit as P

assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,2)
assert D.ACCESS_LEVEL==35 and D.ENDGAME_LEVEL_CAP==60
assert D.operation_locked(79) is False and D.operation_locked(80) is True
assert [P.heat_band(x)['name'] for x in (0,20,40,60,80)]==['نامرئی','زیر ذره‌بین','بازرسی','حکم تعقیب','تعقیب سراسری']
assert P.threat_required(39) is False and P.threat_required(40) is True
assert set(P.THREAT_ORDER)==set(P.MATCHUP_CHANCE) and len(P.ACTION_ORDER)==4
# Every hidden threat has a distinct best specialised counter; blind clicking is materially worse.
for threat in P.THREAT_ORDER:
    scores=P.MATCHUP_CHANCE[threat]
    best=max(scores,key=scores.get)
    assert best==P.THREATS[threat]['counter']
    assert scores[best]-min(scores.values())>=45
# Information and hideout progression improve an informed plan, but do not guarantee it.
for threat in P.THREAT_ORDER:
    action=P.THREATS[threat]['counter']
    blind=P.action_chance(threat,action,heat=70,hideout_level=1,clue_count=0)
    informed=P.action_chance(threat,action,heat=70,hideout_level=5,clue_count=3)
    assert 12<=blind['chance']<informed['chance']<=95
    assert informed['is_counter']
# Resolution is deterministic for a persisted roll and carries meaningful failure consequences.
win=P.resolve_action('camera_net','relocate',0,heat=75,hideout_level=2,clue_count=2)
lose=P.resolve_action('camera_net','fortify',99.99,heat=75,hideout_level=2,clue_count=2)
assert win['success'] and win['heat_delta']<0 and win['is_counter']
assert not lose['success'] and lose['heat_delta']>0 and not lose['is_counter']
assert P.resolve_action('camera_net','relocate',0,heat=75,hideout_level=2,clue_count=2)==win
assert P.resolve_action('tactical_raid','bribe',99.99,heat=90,hideout_level=1,clue_count=0)['jailed']
# Five hideout levels and limited consumable identities.
assert sorted(P.HIDEOUT_LEVELS)==[1,2,3,4,5]
assert P.HIDEOUT_LEVELS[5]['upgrade_cost']==0 and P.FORGED_ID_MAX==3
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8')
service=(ROOT/'app/services/dark_world_pursuit_service.py').read_text(encoding='utf-8')
handler=(ROOT/'app/handlers/dark_world_pursuit.py').read_text(encoding='utf-8')
keyboard=(ROOT/'app/keyboards/dark_world_pursuit_menu.py').read_text(encoding='utf-8')
bot=(ROOT/'bot.py').read_text(encoding='utf-8')
base_service=(ROOT/'app/services/dark_world_service.py').read_text(encoding='utf-8')
case_service=(ROOT/'app/services/dark_world_case_service.py').read_text(encoding='utf-8')
for table in ('dark_world_hideouts','dark_world_pursuit_logs'):assert table in model
for field in ('threat_key','threat_roll_bp','clue_order_json','clues_json','prison_until','forged_ids'):assert field in model and field in service
assert 'secrets.choice' in service and 'secrets.randbelow(10_000)' in service
assert 'Two reliable clues and one plausible false lead' in service
assert 'from app.handlers import dark_world_pursuit' in bot and 'include_router(dark_world_pursuit.router)' in bot
assert 'D.operation_locked' in base_service and 'D.operation_locked' in case_service
for route in ('dwp:hub','dwp:recon','dwp:plans','dwp:plan:','dwp:do:','dwp:upgrade','dwp:buyid','dwp:escape','dwp:break:'):assert route in handler or route in keyboard
for op in ('dwp-recon:{cb.id}','dwp-plan:{cb.id}','dwp-break:{cb.id}', 'f\"dwp-{op}:{cb.id}\"'):assert op in handler
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
# Telegram callback sizes stay safe with owner suffix.
uid='1234567890123456789';callbacks=[]
callbacks += [f'dwp:plan:{k}:{uid}' for k in P.ACTION_ORDER]
callbacks += [f'dwp:do:{k}:{uid}' for k in P.ACTION_ORDER]
callbacks += [f'dwp:break:{k}:{uid}' for k in ('tunnel','papers','riot')]
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for path in files:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
print('OK: Dark World access starts at level 35 while level cap remains 60')
print('OK: hidden persisted threats, mixed clues and asymmetric counterplay')
print('OK: five hideout levels, forged identities, prison and three escape plans')
print('OK: nationwide pursuit gates new operations at Heat 80')
print('OK: owner-bound guarded callbacks and restart-safe audit logs')
print(f'OK: {len(files)} Python files parsed')
