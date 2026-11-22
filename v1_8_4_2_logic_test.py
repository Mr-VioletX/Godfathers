# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace
import ast,sys
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_distribution as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,4,2)
assert len(D.DISTRICTS)==6 and len(D.CHANNELS)==3 and len(D.SCREENS)==3
r=SimpleNamespace(signature_key='solar',value=200_000_000)
direct=D.plan(r,70,70,70,'heights','direct','fast',20,10,1);whole=D.plan(r,70,70,70,'heights','wholesale','reference',20,10,1)
assert direct['qty']<whole['qty'] and direct['heat']>whole['heat']
assert D.resolve(direct,'undercover','reference',40)['success']!=D.resolve(direct,'undercover','fast',40)['success'] or D.SCREENS['reference']['undercover']>D.SCREENS['fast']['undercover']
assert D.undercover_pct('heights',90)>D.undercover_pct('undercity',0)
model=(ROOT/'app/models/dark_world.py').read_text();service=(ROOT/'app/services/dark_world_distribution_service.py').read_text();handler=(ROOT/'app/handlers/dark_world_distribution.py').read_text();bot=(ROOT/'bot.py').read_text()
for t in ('dark_world_distribution_profiles','dark_world_distribution_sales','dark_world_customer_contacts','dark_world_distribution_logs'):assert t in model
for x in ('customer_key','chance_bp','roll_bp','caught','control_points','reputation','debt','deals'):assert x in model
for x in ('secrets.randbelow','team_context','credit_dirty','wallet.trace','dw.heat','DarkWorldCustomerContact'):assert x in service
for x in ('dwd:hub','dwd:products','dwd:districts:','dwd:channels:','dwd:screens:','dwd:start:','dwd:active','dwd:territory','dwd:contacts'):assert x in handler or x in (ROOT/'app/keyboards/dark_world_distribution_menu.py').read_text()
assert 'include_router(dark_world_distribution.router)' in bot
files=list(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: six districts, three channels and three screening strategies')
print('OK: hidden customers, undercover risk, reputation and territorial control')
print('OK: persistent server outcomes, dirty-money payouts, Heat and trace')
print(f'OK: {len(files)} Python files parsed')
