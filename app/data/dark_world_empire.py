# -*- coding: utf-8 -*-
"""Stage 87.14: fictional rivals, inspections and production empire."""
FACILITY_ORDER=("micro_lab","shadow_workshop","ghost_factory")
FACILITIES={
 "micro_lab":{"name":"کارگاه جیبی","icon":"🧪","cost":180_000_000,"capacity":1,"stealth":12,"upkeep":8_000_000},
 "shadow_workshop":{"name":"کارگاه سایه","icon":"🏚️","cost":620_000_000,"capacity":3,"stealth":7,"upkeep":24_000_000},
 "ghost_factory":{"name":"کارخانه شبح","icon":"🏭","cost":1_800_000_000,"capacity":7,"stealth":2,"upkeep":65_000_000},
}
UPGRADES={
 "capacity":{"name":"خط تولید","icon":"⚙️","base_cost":220_000_000},
 "stealth":{"name":"پوشش سایه","icon":"🥷","base_cost":260_000_000},
 "resilience":{"name":"مقاومت شبکه","icon":"🛡️","base_cost":240_000_000},
 "research":{"name":"تحقیق داستانی","icon":"🔬","base_cost":280_000_000},
}
RIVALS={
 "razor":{"name":"اتحادیه تیغ","icon":"🗡️","style":"price","power":58},
 "mirage":{"name":"شبکه سراب","icon":"🪞","style":"intel","power":64},
 "cinder":{"name":"حلقه خاکستر","icon":"🔥","style":"sabotage","power":72},
 "crown":{"name":"دربار خاموش","icon":"♛","style":"control","power":80},
}
RESPONSES={
 "price":{"name":"شکستن قیمت","icon":"📉","cost":40_000_000,"attack":10,"stealth":-3},
 "quality":{"name":"تمرکز کیفیت","icon":"💎","cost":65_000_000,"attack":16,"stealth":2},
 "intel":{"name":"ضداطلاعات","icon":"🛰️","cost":85_000_000,"attack":12,"stealth":10},
}
INSPECTION_CHOICES={
 "pause":{"name":"توقف موقت","icon":"⏸️","cost":10_000_000,"protection":22,"capacity_loss":8},
 "decoy":{"name":"انبار فریب","icon":"🎭","cost":70_000_000,"protection":14,"capacity_loss":0},
 "fortify":{"name":"حفاظت شبکه","icon":"🛡️","cost":110_000_000,"protection":28,"capacity_loss":0},
}
def upgrade_cost(level,key):return round(UPGRADES[key]['base_cost']*(1.58**max(0,int(level))))
def empire_capacity(facilities):return sum(FACILITIES[x.facility_key]['capacity']+int(x.capacity_level or 0)*2 for x in facilities if x.status=='active')
def empire_stealth(facilities):
 return sum(FACILITIES[x.facility_key]['stealth']+int(x.stealth_level or 0)*4 for x in facilities if x.status=='active')
def inspection_risk(heat,trace,facilities):return max(3,min(92,15+int(heat)*.42+int(trace)*.35+len(facilities)*5-empire_stealth(facilities)*.45))
def rival_plan(rival_key,response_key,empire_power,roll):
 r=RIVALS[rival_key];x=RESPONSES[response_key];chance=max(8,min(92,50+empire_power*.35+x['attack']-r['power']*.45));ok=float(roll)<chance;return {'chance':round(chance,2),'success':ok,'control_delta':10 if ok else -8,'heat':3 if ok else 9,'reward':round((r['power']*7_000_000)*(1.15 if response_key=='quality' else 1)) if ok else 0}
def inspection_result(risk,choice_key,resilience,roll):
 x=INSPECTION_CHOICES[choice_key];chance=max(5,min(95,100-float(risk)+x['protection']+int(resilience)*5));ok=float(roll)<chance;return {'chance':round(chance,2),'success':ok,'condition_loss':0 if ok else max(8,32-int(resilience)*3),'confiscation_pct':0 if ok else 18,'heat_delta':-18 if ok else 12}
