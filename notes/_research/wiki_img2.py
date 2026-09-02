import json,sys,re,pathlib
sys.argv=[sys.argv[0]]
exec(open("wiki_img.py").read().split("TERMS = [")[0])   # 复用 get/clean/API/UA
TERMS=[
 ("oslo",         "Oslofjord Norway"),
 ("diamond",      "Breiðamerkursandur icebergs beach"),
 ("ersfjord",     "Ersfjord Senja Norway"),
 ("rorbu",        "Nusfjord Lofoten"),
 ("narvik",       "Ofotfjorden landscape Nordland"),
 ("aurora_lof",   "Aurora borealis Lofoten"),
 ("e10",          "E10 road Lofoten Norway"),
 ("tromso_night", "Tromsø bridge night winter"),
 ("kvalvika",     "Kvalvika beach Lofoten"),
 ("skagsanden",   "Skagsanden beach Flakstad"),
]
out={}
import time
for slug,q in TERMS:
    try:
        d=get({"action":"query","generator":"search","gsrsearch":f"filetype:bitmap {q}",
               "gsrnamespace":6,"gsrlimit":8,"prop":"imageinfo",
               "iiprop":"url|extmetadata|size","iiurlwidth":2000,"format":"json"})
        items=[]
        for p in ((d.get("query") or {}).get("pages") or {}).values():
            ii=(p.get("imageinfo") or [{}])[0]
            if not ii.get("thumburl") or (ii.get("width") or 0)<1400: continue
            md=ii.get("extmetadata") or {}
            lic=clean((md.get("LicenseShortName") or {}).get("value"))
            if lic and re.search(r"non[- ]?free|fair use",lic,re.I): continue
            items.append({"title":p.get("title","").replace("File:",""),"src":ii["thumburl"],
                "w":ii.get("thumbwidth"),"h":ii.get("thumbheight"),"page":ii.get("descriptionurl"),
                "author":clean((md.get("Artist") or {}).get("value")),"license":lic})
        out[slug]={"query":q,"n":len(items),"items":items[:6]}
        print(f"{slug:<14} {len(items):>2}  {items[0]['title'][:56] if items else '— none'}",flush=True)
    except Exception as e:
        out[slug]={"query":q,"error":str(e)[:100],"items":[]}; print(slug,"ERR",e)
    time.sleep(0.35)
pathlib.Path("out_wiki2.json").write_text(json.dumps(out,ensure_ascii=False,indent=1))
