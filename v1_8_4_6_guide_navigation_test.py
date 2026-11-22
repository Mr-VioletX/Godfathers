from pathlib import Path
import ast
R=Path(__file__).parent
assert (R/'VERSION.txt').read_text().strip()=='1.8.4.6'
main=(R/'app/keyboards/dark_world_menu.py').read_text();h=(R/'app/handlers/dark_world.py').read_text()
assert 'GUIDE_PAGES = [' in h and h.count('("')>=9
for route in ('dw:guide:0','dw:guide:{','dw:guide:none','dw:sec:guide','menu:main'):assert route in main+h
assert 'تازه‌واردی؟' in h and 'راهنمای شروع و قوانین' in main
checks={
 'app/keyboards/dark_world_recipes_menu.py':('def catalysts','def signatures','def brands','def modes'),
 'app/keyboards/dark_world_distribution_menu.py':('def districts','def channels','def screens'),
 'app/keyboards/dark_world_smuggling_menu.py':('def packs','def routes','def dests'),
 'app/keyboards/dark_world_empire_menu.py':('def inspections',),
}
for rel,names in checks.items():
 s=(R/rel).read_text()
 for i,name in enumerate(names):
  part=s[s.index(name):]
  part=part[:part.index('\ndef ',1)] if '\ndef ' in part[1:] else part
  assert '◀️' in part or '↩️' in part,(rel,name)
sm=(R/'app/keyboards/dark_world_smuggling_menu.py').read_text();stock=sm[sm.index('def stock'):sm.index('def goods')];assert stock.index('return b.as_markup()')>stock.index('for k in S.GOOD_ORDER') and stock.count('return b.as_markup()')==1
files=list(R.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: nine-page onboarding guide with glass prev/next/back/home navigation')
print('OK: formula discovery, distribution, smuggling and inspection flows all have back paths')
print('OK: smuggling shop no longer returns after its first product')
print(f'OK: {len(files)} Python files parsed')
