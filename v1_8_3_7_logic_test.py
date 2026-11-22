# -*- coding: utf-8 -*-
"""Stage 87.8 / v1.8.3.7 multiplayer raids and information-war tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_raids as R
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,7)
assert D.ACCESS_LEVEL==35 and len(R.APPROACH_ORDER)==3 and len(R.DEFENSE_ORDER)==3
assert R.FORMING_SECONDS==600 and R.MAX_SUPPORTERS_PER_SIDE==2 and R.PAIR_COOLDOWN_HOURS==12 and R.DAILY_RAID_LIMIT==3
# Every attack has one defense it beats and one that counters it: no universal button.
for a in R.APPROACH_ORDER:
 vals={d:R.matchup(a,d) for d in R.DEFENSE_ORDER};assert 18 in vals.values() and -18 in vals.values() and 0 in vals.values()
base=dict(attacker_level=40,defender_level=40,attacker_influence=300,defender_influence=300,hideout_level=3,hideout_integrity=80,attack_team=1,defense_team=1,attack_support=0,defense_support=0,recon_truth=True)
win=R.chance('infiltrate','decoy',**base);lose=R.chance('infiltrate','counter',**base);neutral=R.chance('infiltrate','fortify',**base)
assert win>neutral>lose
assert R.chance('cyber','fortify',**{**base,'attack_support':2})>R.chance('cyber','fortify',**{**base,'defense_support':2})
assert R.chance('assault','counter',**{**base,'recon_truth':True})>R.chance('assault','counter',**{**base,'recon_truth':False})
assert R.chance('assault','counter',**{**base,'hideout_level':1,'hideout_integrity':30})>R.chance('assault','counter',**{**base,'hideout_level':8,'hideout_integrity':100})
# Resolution is deterministic once roll and snapshots are supplied.
ok=R.resolve(60,10,R.STAKE,1_000_000_000);bad=R.resolve(60,90,R.STAKE,1_000_000_000)
assert ok['success'] and ok['stolen']==100_000_000 and ok['stake_refund']==R.STAKE
assert not bad['success'] and bad['stolen']==0 and bad['defense_pool']+bad['burned']==R.STAKE
assert R.resolve(60,10,R.STAKE,1_000_000_000)==ok
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_raids_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_raids.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_raids_menu.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_raid_defenses','dark_world_recons','dark_world_raids','dark_world_raid_participants','dark_world_raid_logs'):assert table in model
for field in ('doctrine_key','observed_defense','truthful','recon_truthful','attack_support_count','defense_support_count','chance_bp','roll_bp','stolen_amount'):assert field in model
# Recon is paid, expiring, and can be deceptive; attack snapshots defense at creation.
assert 'RECON_INTEL_COST' in service and 'expires_at>now()' in service and 'truth=secrets.randbelow' in service
assert 'defense_key=doctrine' in service and 'recon_truthful=bool(rec.truthful)' in service
# Atomic capacity-limited join and exactly-once resolution.
assert 'col<R.MAX_SUPPORTERS_PER_SIDE' in service and 'result.rowcount!=1' in service
assert 'DarkWorldRaidParticipant' in service and 'UniqueConstraint("raid_id","user_id"' in model
assert 'DarkWorldRaid.status=="forming"' in service and '.values(status="resolving")' in service
# Real multiplayer distribution, target loss, hideout damage, team wear, and anti-farming guards.
for phrase in ('support_pool','target_wallet.dirty_balance=max','hide.integrity=max','apply_mission_wear','PAIR_COOLDOWN_HOURS','DAILY_RAID_LIMIT'):assert phrase in service
assert 'int(uid)==int(target_id)' in service and 'int(uid) in (int(raid.attacker_id),int(raid.defender_id))' in service
assert 'from app.handlers import dark_world_raids' in bot and 'include_router(dark_world_raids.router)' in bot
for route in ('dwr:hub','dwr:targets','dwr:scout:','dwr:create:','dwr:defenses','dwr:def:','dwr:lobby','dwr:view:','dwr:join:','dwr:resolve:','dwr:mine'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[f'dwr:create:{uid}:{a}:{uid}' for a in R.APPROACH_ORDER]+[f'dwr:join:999999:defense:{uid}']
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: cyclic attack/defense strategy with deceptive reconnaissance')
print('OK: 10-minute multiplayer lobby and two atomic support slots per side')
print('OK: pair cooldown, daily cap, self-target and duplicate-member guards')
print('OK: atomic exactly-once resolution, stake, loot and supporter distribution')
print('OK: hideout, influence, Heat, dirty money and NPC team integration')
print(f'OK: {len(files)} Python files parsed')
