#!/usr/bin/env python3
import requests
from datetime import datetime
from pathlib import Path

URLs = {
    "CT": "https://ispip.clang.cn/chinatelecom.txt",
    "CU": "https://ispip.clang.cn/unicom_cnc.txt",
    "CM": "https://ispip.clang.cn/cmcc.txt",
}

CHUNK_SIZE = 600
TODAY = datetime.now().strftime("%Y-%m-%d")
SCRIPT_DIR = Path(__file__).parent

def fetch_routes(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = [line.strip() for line in response.text.split('\n') if '/' in line]
        return lines
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

def generate_config(isp, lines):
    output = []
    AG = f"zzz_ISPAG_{isp}"
    output.append("config firewall address")
    
    members = []
    for index, line in enumerate(lines):
        parts = line.split('/')
        if len(parts) != 2:
            continue
        ip, mask = parts[0], parts[1]
        bg_num = (index // CHUNK_SIZE) + 1
        obj_name = f"zzz_ISP_{isp}_{bg_num}_{ip}_{mask}"
        members.append(obj_name)
        output.append(f'edit "{obj_name}"')
        output.append(f'    set subnet {ip}/{mask}')
        output.append('    set allow-routing enable')
        output.append(f'    set comment "update-date: {TODAY}"')
        output.append('next')
    
    output.append("end\n")
    
    bg_count = (len(lines) + CHUNK_SIZE - 1) // CHUNK_SIZE
    bg_list = []
    
    for g in range(1, bg_count + 1):
        bg_name = f"zzz_ISPBG_{isp}_{g}"
        bg_list.append(bg_name)
        chunk_members = [m for m in members if int(m.split('_')[3]) == g]
        if chunk_members:
            output.append("config firewall addrgrp")
            output.append(f'    edit "{bg_name}"')
            output.append('        unset member')
            member_str = ' '.join([f'"{m}"' for m in chunk_members])
            output.append(f'        set member {member_str}')
            output.append('        set allow-routing enable')
            output.append('    next')
            output.append("end\n")
    
    if bg_list:
        output.append("config firewall addrgrp")
        output.append(f'    edit "{AG}"')
        output.append('        unset member')
        bg_str = ' '.join([f'"{bg}"' for bg in bg_list])
        output.append(f'        set member {bg_str}')
        output.append('        set allow-routing enable')
        output.append('    next')
        output.append("end\n")
    
    return '\n'.join(output)

def main():
    for isp, url in URLs.items():
        print(f"Fetching {isp} routes...")
        lines = fetch_routes(url)
        if not lines:
            print(f"  No routes found for {isp}")
            continue
        config = generate_config(isp, lines)
        outfile = SCRIPT_DIR / f"fortios_isp_{isp}.conf.txt"
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(config)
        print(f"OK: {outfile} ({len(lines)} routes)")

if __name__ == "__main__":
    main()
