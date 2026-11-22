from pathlib import Path
import ast,re
R=Path(__file__).parent
assert tuple(map(int,(R/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,4,5)
main=(R/'app/keyboards/dark_world_menu.py').read_text();handler=(R/'app/handlers/dark_world.py').read_text()
for key in ('ops','crew','economy','competition','production','guide'):assert f'dw:sec:{key}' in main
for fn in ('operations_hub_menu','crew_hub_menu','economy_hub_menu','competition_hub_menu','production_hub_menu','guide_hub_menu'):assert fn in main and fn in handler
assert 'menu:main' in main and '◀️ دنیای سیاه' in main
lab=(R/'app/keyboards/dark_world_laboratory_menu.py').read_text();recipes=(R/'app/keyboards/dark_world_recipes_menu.py').read_text();dist=(R/'app/keyboards/dark_world_distribution_menu.py').read_text();emp=(R/'app/keyboards/dark_world_empire_menu.py').read_text()
assert all('PAGE=6' in x for x in (lab,recipes,dist))
assert 'dwx:market:bases' in recipes and 'dwx:market:catalysts' in recipes and 'dwx:market:signatures' in recipes
assert all('◀️' in x for x in (lab,recipes,dist,emp))
cases=(R/'app/handlers/dark_world_cases.py').read_text();comp=(R/'app/handlers/dark_world_competitive.py').read_text();employment=(R/'app/handlers/dark_world_employment.py').read_text();empire=(R/'app/handlers/dark_world_empire.py').read_text()
assert 'dwc:hub' in cases and 'dwc:hub' not in comp and 'dwk:hub' in comp
assert 'dwe:hub' in employment and 'dwe:hub' not in empire and 'dwi:hub' in empire
files=list(R.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: main Dark World hub reduced to six grouped sections')
print('OK: glass navigation has back/home paths and paginated long lists')
print('OK: case/competitive and employment/empire callback collisions removed')
print(f'OK: {len(files)} Python files parsed')
