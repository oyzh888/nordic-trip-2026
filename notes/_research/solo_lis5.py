#!/usr/bin/env python3
"""里斯本周日回（10/13–10/18，5 晚）的 Airbnb 行情，只翻 3 页做对比。"""
import json, sys
import abnb_interest as AI
AI.CITIES = {"lis": ("2026-10-13", "2026-10-18", AI.CITIES["lis"][2], AI.CITIES["lis"][3])}
sys.argv = [sys.argv[0], sys.argv[1], "3", "lis"]
AI.main()
