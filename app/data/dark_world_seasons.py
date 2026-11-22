# -*- coding: utf-8 -*-
"""Stage 87.9 — persistent collective narrative seasons."""
from __future__ import annotations
SEASON_HOURS_PER_CHAPTER=24
CHAPTER_COUNT=4
INTEL_CONTRIBUTION=10
DIRTY_CONTRIBUTION=50_000_000
FACTION_ORDER=("union","iron","glass")
FACTIONS={
 "union":{"name":"اتحادیه سایه","icon":"🕶️","perk":"+۵٪ درآمد محموله","market_pct":5,"raid":0,"finance":0,"recon":0},
 "iron":{"name":"پیمان آهن","icon":"⚔️","perk":"+۴ قدرت شبیخون","market_pct":0,"raid":4,"finance":0,"recon":0},
 "glass":{"name":"حلقه شیشه","icon":"🔮","perk":"+۱۰٪ دقت شناسایی و +۳ پول‌شویی","market_pct":0,"raid":0,"finance":3,"recon":10},
}
CHAPTERS=(
 {"title":"خاموشی بندر","story":"چراغ‌های بندر خاموش شده‌اند و سه جناح برای کنترل مسیر تصمیم می‌گیرند.","choices":{"open":{"name":"بازکردن مسیر عمومی","effect":"عرضه بیشتر و سود قاچاق کمتر","market_pct":-6,"finance":2,"raid":0},"seal":{"name":"محاصره اسکله","effect":"کمیابی و سود قاچاق بیشتر","market_pct":10,"finance":-2,"raid":2},"ghost":{"name":"مسیرهای نامرئی","effect":"کاهش بازرسی مالی","market_pct":2,"finance":7,"raid":-1}}},
 {"title":"دفتر سوخته","story":"دفتر بدهی واسطه‌ها پیدا شده؛ افشا، نابودی یا استفاده پنهانی مسیر فصل را تغییر می‌دهد.","choices":{"expose":{"name":"افشای دفتر","effect":"پول‌شویی دشوار، اطلاعات دقیق‌تر","market_pct":0,"finance":-7,"raid":2},"burn":{"name":"سوزاندن دفتر","effect":"ردگیری کمتر و اقتصاد متعادل","market_pct":1,"finance":5,"raid":0},"leverage":{"name":"باج‌گیری هدفمند","effect":"درآمد و درگیری بیشتر","market_pct":6,"finance":1,"raid":5}}},
 {"title":"شهر بی‌صدا","story":"یک شب بدون ارتباط فرا رسیده و انتخاب جمعی، قواعد نبرد را تعیین می‌کند.","choices":{"truce":{"name":"آتش‌بس شبانه","effect":"کاهش مزیت حمله","market_pct":4,"finance":3,"raid":-7},"hunt":{"name":"شکار هماهنگ","effect":"شبیخون‌ها تهاجمی‌تر می‌شوند","market_pct":-2,"finance":-2,"raid":9},"listen":{"name":"شنود خاموش","effect":"اقتصاد آرام و اطلاعات بیشتر","market_pct":2,"finance":5,"raid":1}}},
 {"title":"تاج سیاه","story":"فصل به پایان نزدیک است؛ شهر میان تمرکز قدرت، تقسیم قلمرو یا هرج‌ومرج انتخاب می‌کند.","choices":{"crown":{"name":"یک فرمانروای سایه","effect":"ریسک و سود بالا","market_pct":9,"finance":-5,"raid":7},"council":{"name":"شورای سه‌گانه","effect":"ثبات و کارمزد کمتر","market_pct":4,"finance":6,"raid":1},"chaos":{"name":"شهر بی‌تاج","effect":"بازار نوسانی و نبرد آزاد","market_pct":12,"finance":-8,"raid":10}}},
)
def chapter(i):return CHAPTERS[max(0,min(len(CHAPTERS)-1,int(i)))]
def vote_weight(influence):return 1+min(4,max(0,int(influence))//500)
def apply_choice(market,finance,raid,choice):return {"market_pct":max(-20,min(25,int(market)+int(choice["market_pct"]))),"finance":max(-15,min(15,int(finance)+int(choice["finance"]))),"raid":max(-15,min(15,int(raid)+int(choice["raid"])))}
