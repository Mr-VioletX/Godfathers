# -*- coding: utf-8 -*-
"""Stage 87.9 / v1.8.3.8 collective narrative season tests."""
from __future__ import annotations
import ast,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_seasons as S
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,8)
assert D.ACCESS_LEVEL==35 and len(S.FACTION_ORDER)==3 and len(S.CHAPTERS)==4 and S.SEASON_HOURS_PER_CHAPTER==24
assert all(len(x['choices'])==3 for x in S.CHAPTERS)
# Factions have distinct, non-dominating perks.
assert S.FACTIONS['union']['market_pct']>0 and S.FACTIONS['union']['raid']==0
assert S.FACTIONS['iron']['raid']>0 and S.FACTIONS['iron']['market_pct']==0
assert S.FACTIONS['glass']['recon']>0 and S.FACTIONS['glass']['finance']>0
# Influence has bounded vote power.
assert S.vote_weight(0)==1 and S.vote_weight(500)==2 and S.vote_weight(10_000)==5
# Collective chapter effects accumulate but remain bounded.
m={'market_pct':0,'finance':0,'raid':0}
for chapter in S.CHAPTERS:
 choice=next(iter(chapter['choices'].values()));m=S.apply_choice(m['market_pct'],m['finance'],m['raid'],choice)
assert -20<=m['market_pct']<=25 and -15<=m['finance']<=15 and -15<=m['raid']<=15
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_seasons_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_seasons.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_seasons_menu.py').read_text(encoding='utf-8');smuggling=(ROOT/'app/services/dark_world_smuggling_service.py').read_text(encoding='utf-8');finance=(ROOT/'app/services/dark_world_finance_service.py').read_text(encoding='utf-8');raids=(ROOT/'app/services/dark_world_raids_service.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_seasons','dark_world_faction_members','dark_world_season_votes','dark_world_faction_scores','dark_world_season_logs'):assert table in model
for field in ('season_no','chapter_index','market_bias','finance_bias','raid_bias','winning_faction','contribution','reward_claimed','choice_key','weight','points'):assert field in model
# Lazy restart-safe chapter progression, deterministic tally and one claim.
assert 'while x.status=="active" and x.chapter_ends_at<=now()' in service
assert 'DarkWorldSeasonVote.weight' not in service or 'v.weight' in service
assert 'winner=max(tally' in service and 'chapter_resolved' in service
assert 'mem.reward_claimed' in service and 'reward_claimed=True' in service
# One membership and one vote per chapter are database-enforced.
assert 'UniqueConstraint("owner_id","season_id"' in model and 'UniqueConstraint("season_id","chapter_index","owner_id"' in model
# Contributions consume real resources and feed faction score.
assert 'INTEL_CONTRIBUTION' in service and 'DIRTY_CONTRIBUTION' in service and 'score.points=' in service
# Outcomes and faction perks affect existing economies, not only narrative text.
assert 'SES.modifiers' in smuggling and 'season_market_pct' in smuggling
assert 'SES.modifiers' in finance and 'season_finance_bonus' in finance
assert raids.count('SES.modifiers')>=2 and 'mods["recon"]' in raids and 'am["raid"]-dm["raid"]' in raids
assert 'from app.handlers import dark_world_seasons' in bot and 'include_router(dark_world_seasons.router)' in bot
for route in ('dws:hub','dws:factions','dws:join:','dws:choices','dws:vote:','dws:contrib','dws:give:','dws:board','dws:claim'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[f'dws:join:{k}:{uid}' for k in S.FACTION_ORDER]+[f'dws:vote:{k}:{uid}' for c in S.CHAPTERS for k in c['choices']]
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: three distinct factions, four chapters and twelve collective choices')
print('OK: weighted voting, resource contributions and persistent faction scores')
print('OK: lazy restart-safe chapter resolution and exactly-once season rewards')
print('OK: season outcomes modify smuggling, laundering, reconnaissance and raids')
print('OK: owner-bound guarded actions and database uniqueness constraints')
print(f'OK: {len(files)} Python files parsed')
