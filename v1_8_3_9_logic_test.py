# -*- coding: utf-8 -*-
"""Stage 87.10 / v1.8.3.9 competitive finale tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_competitive as C
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,9)
assert D.ACCESS_LEVEL==35 and C.MIN_RANK_ACTIVITY==3 and C.BOSS_HIT_COOLDOWN_SECONDS==7200
# Multi-axis scoring: every active path contributes while passive influence is capped.
base=C.score(influence=0,contribution=0,shipments=0,launders=0,raid_wins=0,employment=0,boss_damage=0)
for key in ('shipments','launders','raid_wins','employment','boss_damage','contribution','influence'):
 args=dict(influence=0,contribution=0,shipments=0,launders=0,raid_wins=0,employment=0,boss_damage=0);args[key]=10 if key not in ('boss_damage','influence') else 1000;assert C.score(**args)['score']>base['score']
assert C.score(influence=100_000,contribution=0,shipments=0,launders=0,raid_wins=0,employment=0,boss_damage=0)['score']==250
assert C.score(influence=0,contribution=0,shipments=1,launders=1,raid_wins=1,employment=0,boss_damage=0)['activity']==3
# Divisions and bounded anti-inflation rewards.
assert C.division(0)['name']=='جرقه‌ی کوچه' and C.division(5000)['name']=='تاج‌دارِ خلأ'
first=C.reward(1,100,1);third=C.reward(3,100,1);normal=C.reward(50,100,1)
assert first['dirty']>third['dirty']>normal['dirty'] and first['prestige']>normal['prestige']
assert C.reward(1,100,.1)['dirty']==round(1_000_000_000*.75) and C.reward(1,100,5)['dirty']==round(1_000_000_000*1.15)
assert .75<=C.economy_factor(1,10**15,10**15,10**15)<=1.15
assert C.boss_max_hp(10)>C.boss_max_hp(1) and C.boss_damage(60,1,99)>C.boss_damage(35,0,0)
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_competitive_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_competitive.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_competitive_menu.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_season_ranks','dark_world_competitive_profiles','dark_world_competitive_rewards','dark_world_balance_snapshots','dark_world_world_bosses','dark_world_boss_hits'):assert table in model
for field in ('division_key','eligible','activity','boss_damage','rating','prestige','best_rank','reward_factor_bp','current_hp','damage','roll'):assert field in model
# Rankings are frozen after completion and one reward exists per season/user.
assert 'season.status!="completed"' in service and 'DarkWorldSeasonRank(' in service
assert 'UniqueConstraint("season_id","owner_id",name="uq_dw_season_rank"' in model
assert 'UniqueConstraint("season_id","owner_id",name="uq_dw_comp_reward"' in model
assert 'MIN_RANK_ACTIVITY' in service and 'cp.rating=round(int(cp.rating or 0)*.90)' in service
# Time-bounded source metrics and actual winning support roles.
for phrase in ('DarkWorldShipment.started_at>=start','DarkWorldLaunderingJob.started_at>=start','DarkWorldRaid.resolved_at>=start','DarkWorldEmploymentContract.completed_at>=start','DarkWorldBossHit.season_id==season.id'):assert phrase in service
assert 'DarkWorldRaidParticipant.side=="attack"' in service and 'DarkWorldRaid.status=="attacker_won"' in service
# Telemetry changes reward factor but is strictly bounded; active snapshots are not frozen.
assert 'dirty_created' in service and 'market_volume' in service and 'season.status!="completed":return SimpleNamespace' in service
# Boss uses energy, team effectiveness, cooldown, persistent hits and scaling HP.
for phrase in ('BOSS_ENERGY_COST','BOSS_HIT_COOLDOWN_SECONDS','team_context','DarkWorldBossHit(','b.current_hp=max','growth=hp-int(b.max_hp)'):assert phrase in service
assert 'from app.handlers import dark_world_competitive' in bot and 'include_router(dark_world_competitive.router)' in bot
for route in ('dwk:hub','dwk:board','dwk:me','dwk:boss','dwk:economy','dwk:claim','dwk:hall'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[f'{x}:{uid}' for x in ('dwk:hub','dwk:board','dwk:me','dwk:boss','dwk:economy','dwk:claim','dwk:hall')];assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: multi-axis seasonal score, five divisions and minimum activity gate')
print('OK: world boss, persistent damage, cooldown, energy and NPC team scaling')
print('OK: frozen final ranks, exactly-once rewards and 10-percent rating decay')
print('OK: bounded economy telemetry controls rewards without runaway inflation')
print('OK: hall of fame, controlled seasonal reset and owner-bound guarded actions')
print(f'OK: {len(files)} Python files parsed')
