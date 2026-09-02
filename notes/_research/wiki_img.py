#!/usr/bin/env python3
"""Wikimedia Commons 风光图抓取：自由授权 + 带作者/许可，可直链热引用。"""
import json, sys, time, urllib.parse, urllib.request, pathlib, re

API = "https://commons.wikimedia.org/w/api.php"
UA = "nordic-trip-2026/1.0 (personal trip planning; contact zouyang@adobe.com)"

TERMS = [
 ("oslo",        "Oslo Norway autumn skyline"),
 ("hallgrim",    "Hallgrímskirkja Reykjavik"),
 ("rvk",         "Reykjavik harbour panorama"),
 ("sunvoyager",  "Sun Voyager Solfar Reykjavik"),
 ("seljalands",  "Seljalandsfoss"),
 ("skogafoss",   "Skógafoss"),
 ("dyrholaey",   "Dyrhólaey Iceland"),
 ("reynisfjara", "Reynisfjara black sand beach"),
 ("jokulsarlon", "Jökulsárlón glacier lagoon"),
 ("diamond",     "Diamond Beach Breiðamerkursandur"),
 ("vestrahorn",  "Vestrahorn Stokksnes"),
 ("svartifoss",  "Svartifoss Skaftafell"),
 ("fjallsarlon", "Fjallsárlón"),
 ("gullfoss",    "Gullfoss"),
 ("geysir",      "Strokkur geyser Haukadalur"),
 ("thingvellir", "Þingvellir national park rift"),
 ("kerid",       "Kerið crater lake"),
 ("bluelagoon",  "Blue Lagoon Iceland geothermal spa"),
 ("gunnuhver",   "Gunnuhver Reykjanes"),
 ("brimketill",  "Brimketill Iceland"),
 ("bridge2cont", "Bridge between continents Reykjanes"),
 ("reykjanesviti","Reykjanesviti lighthouse"),
 ("kirkjufell",  "Kirkjufell Snæfellsnes"),
 ("aurora_is",   "Aurora borealis Iceland northern lights"),
 ("lofoten",     "Lofoten islands panorama"),
 ("svolvaer",    "Svolvær Lofoten"),
 ("henningsvaer","Henningsvær Lofoten"),
 ("reine",       "Reine Lofoten Norway"),
 ("hamnoy",      "Hamnøy Lofoten rorbuer"),
 ("reinebringen","Reinebringen view Lofoten"),
 ("sakrisoy",    "Sakrisøy Lofoten"),
 ("haukland",    "Haukland beach Lofoten"),
 ("narvik",      "Narvik Ofotfjord Norway"),
 ("tromso",      "Tromsø city panorama"),
 ("arcticcath",  "Arctic Cathedral Tromsdalen"),
 ("fjellheisen", "Tromsø view from Storsteinen"),
 ("aurora_no",   "Aurora borealis Tromsø northern lights Norway"),
 ("senja",       "Senja Norway landscape"),
 ("segla",       "Segla Senja"),
 ("tungeneset",  "Tungeneset Senja"),
 ("bergsbotn",   "Bergsbotn Senja viewpoint"),
 ("ersfjord",    "Ersfjordstranda Senja beach"),
 ("rorbu",       "Rorbu Norway fishing cabin red"),
]

def get(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())

def clean(s):
    if not s: return None
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()[:120]

out = {}
for slug, q in TERMS:
    try:
        d = get({"action":"query","generator":"search","gsrsearch":f"filetype:bitmap {q}",
                 "gsrnamespace":6,"gsrlimit":8,"prop":"imageinfo",
                 "iiprop":"url|extmetadata|size","iiurlwidth":2000,"format":"json"})
        pages = (d.get("query") or {}).get("pages") or {}
        items = []
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            if not ii.get("thumburl"): continue
            if (ii.get("width") or 0) < 1400: continue
            md = ii.get("extmetadata") or {}
            lic = clean((md.get("LicenseShortName") or {}).get("value"))
            # 排除限制性许可
            if lic and re.search(r"non[- ]?free|fair use", lic, re.I): continue
            items.append({
                "title": p.get("title","").replace("File:",""),
                "src": ii["thumburl"], "w": ii.get("thumbwidth"), "h": ii.get("thumbheight"),
                "page": ii.get("descriptionurl"),
                "author": clean((md.get("Artist") or {}).get("value")),
                "license": lic,
            })
        out[slug] = {"query": q, "n": len(items), "items": items[:6]}
        print(f"{slug:<14} {len(items):>2}  {items[0]['title'][:52] if items else '— none'}", flush=True)
    except Exception as e:
        out[slug] = {"query": q, "error": f"{type(e).__name__}: {e}"[:120], "items": []}
        print(f"{slug:<14} ERR {e}", flush=True)
    time.sleep(0.35)

pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "out_wiki.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1))
print("\ntotal:", sum(len(v.get("items",[])) for v in out.values()), "images across", len(out), "terms")
