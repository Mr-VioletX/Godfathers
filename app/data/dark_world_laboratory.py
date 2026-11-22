# -*- coding: utf-8 -*-
"""Stage 87.11 — fictional-only abstract laboratory game data.
No real substances, chemistry, ingredients, temperatures, or production steps exist here.
"""
from __future__ import annotations
LAB_MAX_LEVEL=10
MATERIAL_PACK_QTY=10
MATERIALS={
 "a":{"name":"بستر A خیالی","icon":"🔷","price":40_000_000},
 "b":{"name":"عامل B خیالی","icon":"🔶","price":65_000_000},
 "c":{"name":"پایدارساز C خیالی","icon":"🟣","price":90_000_000},
 "d":{"name":"رنگ‌مایه D خیالی","icon":"🟢","price":120_000_000},
}
PRODUCT_ORDER=("nocturne","neon","echo","velvet","ember","prism","lunar","static","obsidian","mirage","aurora","void")
PRODUCTS={
 "nocturne":{"name":"شب‌تاب نوکتورن","icon":"🌘","family":"مه داستانی","level":1,"base":80_000_000,"duration":900,"risk":5,"power":35,"stability":80,"recipe":{"a":2,"b":1}},
 "neon":{"name":"شکوفه نئون","icon":"🌺","family":"بلور داستانی","level":1,"base":95_000_000,"duration":1100,"risk":7,"power":42,"stability":72,"recipe":{"a":1,"b":2}},
 "echo":{"name":"پژواک آبی","icon":"🔊","family":"کپسول داستانی","level":2,"base":120_000_000,"duration":1300,"risk":9,"power":48,"stability":76,"recipe":{"a":2,"c":1}},
 "velvet":{"name":"مه مخملی","icon":"🪻","family":"مه داستانی","level":2,"base":135_000_000,"duration":1500,"risk":10,"power":50,"stability":84,"recipe":{"b":2,"c":1}},
 "ember":{"name":"جرقه سرخ","icon":"🔥","family":"عصاره داستانی","level":3,"base":165_000_000,"duration":1700,"risk":14,"power":63,"stability":60,"recipe":{"a":2,"b":1,"c":1}},
 "prism":{"name":"منشور هفت‌رنگ","icon":"🔮","family":"بلور داستانی","level":3,"base":190_000_000,"duration":1900,"risk":13,"power":58,"stability":78,"recipe":{"a":1,"c":2,"d":1}},
 "lunar":{"name":"قطره مهتاب","icon":"🌙","family":"عصاره داستانی","level":4,"base":230_000_000,"duration":2200,"risk":16,"power":68,"stability":86,"recipe":{"b":2,"c":2,"d":1}},
 "static":{"name":"غبار استاتیک","icon":"⚡","family":"پودر داستانی","level":5,"base":285_000_000,"duration":2500,"risk":20,"power":77,"stability":55,"recipe":{"a":3,"b":2,"d":1}},
 "obsidian":{"name":"ابسیدین خواب","icon":"🖤","family":"بلور داستانی","level":6,"base":350_000_000,"duration":2900,"risk":22,"power":82,"stability":69,"recipe":{"a":2,"c":2,"d":2}},
 "mirage":{"name":"سراب طلایی","icon":"🏜️","family":"کپسول داستانی","level":7,"base":430_000_000,"duration":3300,"risk":25,"power":79,"stability":90,"recipe":{"b":3,"c":2,"d":2}},
 "aurora":{"name":"شفق مایع","icon":"🌌","family":"عصاره داستانی","level":8,"base":540_000_000,"duration":3800,"risk":29,"power":91,"stability":74,"recipe":{"a":3,"b":2,"c":2,"d":2}},
 "void":{"name":"بلور خلأ","icon":"🕳️","family":"بلور داستانی","level":10,"base":750_000_000,"duration":4500,"risk":35,"power":100,"stability":62,"recipe":{"a":3,"b":3,"c":3,"d":3}},
}
MODE_ORDER=("safe","precise","rush")
MODES={
 "safe":{"name":"چرخه ایمن","icon":"🛡️","quality":-2,"risk":-10,"duration":1.35,"yield":1.0,"condition":2},
 "precise":{"name":"چرخه دقیق","icon":"🎛️","quality":8,"risk":0,"duration":1.0,"yield":1.0,"condition":4},
 "rush":{"name":"چرخه فشرده","icon":"⚠️","quality":2,"risk":14,"duration":.60,"yield":1.25,"condition":9},
}
UPGRADES={"equipment":{"name":"تجهیزات","icon":"🧰"},"power":{"name":"برق پایدار","icon":"⚡"},"ventilation":{"name":"تهویه","icon":"🌀"},"safety":{"name":"ایمنی","icon":"🧯"}}
def upgrade_cost(current):return 160_000_000*max(1,int(current))**2
def capacity(level,equipment):return 5+int(level)*2+int(equipment)
def plan(product_key,qty,mode_key,lab):
 p=PRODUCTS.get(product_key);m=MODES.get(mode_key);q=max(1,min(10,int(qty)))
 if not p or not m:return {}
 equipment=int(lab.equipment);power=int(lab.power);vent=int(lab.ventilation);safety=int(lab.safety);condition=int(lab.condition)
 chance=max(20,min(98,92-p['risk']+safety*2+vent*1.4+(condition-50)*.12-m['risk']))
 quality=max(15,min(100,45+equipment*4+power*2+m['quality']));potency=max(10,min(100,p['power']+power*2));stability=max(10,min(100,p['stability']+vent*2+safety));yield_qty=max(1,round(q*m['yield']));duration=round(p['duration']*q**.45*m['duration']);materials={k:v*q for k,v in p['recipe'].items()}
 return {"product_key":product_key,"qty":q,"mode_key":mode_key,"chance":round(chance,2),"quality":quality,"potency":potency,"stability":stability,"yield_qty":yield_qty,"duration":duration,"materials":materials,"condition_loss":m['condition']+round(p['risk']/10)}
def resolve(plan,roll,quality_roll,potency_roll,stability_roll):
 success=float(roll)<float(plan['chance']);adj=lambda base,r:max(1,min(100,round(base+(float(r)-50)/10)))
 return {"success":success,"yield_qty":plan['yield_qty'] if success else 0,"quality":adj(plan['quality'],quality_roll),"potency":adj(plan['potency'],potency_roll),"stability":adj(plan['stability'],stability_roll),"accident":not success,"condition_loss":plan['condition_loss']+(8 if not success else 0)}
def broker_value(product_key,quality,potency,stability):
 p=PRODUCTS[product_key];factor=.55+int(quality)/300+int(potency)/500+int(stability)/600;return round(p['base']*factor)


# Stage 87.12 catalog expansion — still entirely fictional.
_EXTRA={
 "comet":{"name":"دنباله‌دار سپید","icon":"☄️","family":"پودر داستانی","level":2,"base":145_000_000,"duration":1450,"risk":11,"power":55,"stability":70,"recipe":{"a":1,"b":1,"d":1}},
 "tide":{"name":"موج کبود","icon":"🌊","family":"عصاره داستانی","level":3,"base":175_000_000,"duration":1800,"risk":13,"power":57,"stability":85,"recipe":{"a":2,"c":1,"d":1}},
 "halo":{"name":"هاله خاموش","icon":"⭕","family":"مه داستانی","level":4,"base":215_000_000,"duration":2050,"risk":15,"power":64,"stability":82,"recipe":{"b":1,"c":2,"d":1}},
 "raven":{"name":"پر کلاغ","icon":"🪶","family":"پودر داستانی","level":4,"base":245_000_000,"duration":2300,"risk":18,"power":72,"stability":68,"recipe":{"a":2,"b":2,"d":1}},
 "quartz":{"name":"کوارتز نجوا","icon":"💠","family":"بلور داستانی","level":5,"base":300_000_000,"duration":2600,"risk":19,"power":70,"stability":88,"recipe":{"a":2,"c":2,"d":1}},
 "eclipse":{"name":"قطره خسوف","icon":"🌑","family":"عصاره داستانی","level":6,"base":365_000_000,"duration":3000,"risk":23,"power":84,"stability":66,"recipe":{"b":3,"c":1,"d":2}},
 "siren":{"name":"آواز سیرن","icon":"🎶","family":"کپسول داستانی","level":6,"base":390_000_000,"duration":3150,"risk":24,"power":76,"stability":92,"recipe":{"a":2,"b":2,"c":2}},
 "glacier":{"name":"یخچال شیشه‌ای","icon":"🧊","family":"بلور داستانی","level":7,"base":455_000_000,"duration":3450,"risk":26,"power":83,"stability":94,"recipe":{"a":3,"c":2,"d":2}},
 "phoenix":{"name":"خاکستر ققنوس","icon":"🦅","family":"پودر داستانی","level":8,"base":570_000_000,"duration":3900,"risk":31,"power":96,"stability":61,"recipe":{"a":3,"b":3,"d":2}},
 "zenith":{"name":"اوج بنفش","icon":"🔺","family":"کپسول داستانی","level":9,"base":650_000_000,"duration":4200,"risk":33,"power":94,"stability":81,"recipe":{"b":3,"c":3,"d":2}},
 "singularity":{"name":"تکینگی مخملی","icon":"🌀","family":"مه داستانی","level":10,"base":820_000_000,"duration":4800,"risk":38,"power":100,"stability":73,"recipe":{"a":3,"b":3,"c":2,"d":3}},
 "crown":{"name":"تاج بی‌صدا","icon":"♛","family":"بلور داستانی","level":10,"base":900_000_000,"duration":5100,"risk":40,"power":98,"stability":96,"recipe":{"a":4,"b":3,"c":3,"d":3}},
}
PRODUCTS.update(_EXTRA)
PRODUCT_ORDER=PRODUCT_ORDER+tuple(_EXTRA)
