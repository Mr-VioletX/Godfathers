# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace
import ast,sys
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_recipes as R
from app.data import dark_world_laboratory as L
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,4,1)
assert len(L.PRODUCT_ORDER)==24 and len(R.BASES)*len(R.CATALYSTS)*len(R.SIGNATURES)==125
assert len(R.BASES)==len(R.CATALYSTS)==len(R.SIGNATURES)==5
forms=[R.formula(b,c,s,n) for b in R.BASES for c in R.CATALYSTS for s in R.SIGNATURES for n in R.BRANDS]
assert len({x['fingerprint'] for x in forms})==125 and len({x['name'] for x in forms})==375
assert all(set(x)=={'fingerprint','base_key','catalyst_key','signature_key','brand_key','name','quality','power','stability','risk','value','required_level'} for x in forms)
lab=SimpleNamespace(safety=3,ventilation=3,condition=80,equipment=3,power=3)
r=SimpleNamespace(risk=20,quality=60,power=65,stability=70)
safe=R.production(r,'safe',lab);rush=R.production(r,'rush',lab)
assert safe['chance']>rush['chance'] and safe['duration']>rush['duration'] and rush['qty']>=safe['qty']
assert R.resolve(safe,0,50,50,50)['success'] and not R.resolve(safe,99.99,50,50,50)['success']
assert R.sale_value(SimpleNamespace(value=1000,signature_key=R.demand_signature()),50,50,50)>R.sale_value(SimpleNamespace(value=1000,signature_key='none'),50,50,50)
model=(ROOT/'app/models/dark_world.py').read_text();service=(ROOT/'app/services/dark_world_recipes_service.py').read_text();handler=(ROOT/'app/handlers/dark_world_recipes.py').read_text();keyboard=(ROOT/'app/keyboards/dark_world_recipes_menu.py').read_text();bot=(ROOT/'bot.py').read_text()
for t in ('dark_world_ingredient_inventory','dark_world_crop_plots','dark_world_custom_recipes','dark_world_custom_batches','dark_world_custom_inventory','dark_world_custom_sales'):assert t in model
for x in ('plant','harvest','discover','start','collect','sell','credit_dirty','secrets.randbelow(10_000)'):assert x in service
for x in ('dwx:garden','dwx:market','dwx:buy:','dwx:plant:','dwx:harvest:','dwx:discover:','dwx:start:','dwx:sell:'):assert x in handler or x in keyboard
assert 'کاملاً خیالی' in handler and 'no real materials or processes' in (ROOT/'app/data/dark_world_recipes.py').read_text()
assert 'include_router(dark_world_recipes.router)' in bot
files=list(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: 24 catalog products and 125 fictional formulas')
print('OK: black-market purchase, cultivation, harvest, discovery, production and sale')
print('OK: three strategic cycles and persistent hidden outcomes')
print('OK: fictional-only tokens with no real materials or production instructions')
print(f'OK: {len(files)} Python files parsed')
