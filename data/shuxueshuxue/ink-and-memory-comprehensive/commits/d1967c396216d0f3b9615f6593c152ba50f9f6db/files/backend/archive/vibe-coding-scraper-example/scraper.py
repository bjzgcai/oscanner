#!/usr/bin/env python3
"""Scrape Disco Elysium skill pages."""

import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json
import time

SKILLS = [
    "Logic", "Encyclopedia", "Rhetoric", "Drama", "Conceptualization", "Visual_Calculus",
    "Volition", "Inland_Empire", "Empathy", "Authority", "Esprit_de_Corps", "Suggestion",
    "Endurance", "Pain_Threshold", "Physical_Instrument", "Electrochemistry", "Shivers", "Half_Light",
    "Hand-Eye_Coordination", "Perception", "Reaction_Speed", "Savoir_Faire", "Interfacing", "Composure"
]

OUTPUT_DIR = Path(__file__).parent / "references"

def scrape_skill(skill_name: str) -> dict:
    url = f"https://discoelysium.fandom.com/wiki/{skill_name}"
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')

    content = soup.find('div', {'class': 'mw-parser-output'})
    paragraphs = [p.get_text().strip() for p in content.find_all('p') if p.get_text().strip()]

    return {
        "name": skill_name.replace('_', ' '),
        "description": '\n\n'.join(paragraphs[:3])
    }

OUTPUT_DIR.mkdir(exist_ok=True)
skills_data = {}

for skill in SKILLS:
    print(f"Scraping {skill}...")
    skills_data[skill] = scrape_skill(skill)
    time.sleep(0.5)

with open(OUTPUT_DIR / "disco_skills.json", 'w', encoding='utf-8') as f:
    json.dump(skills_data, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done")
