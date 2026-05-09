#!/usr/bin/env python3
import requests
from datetime import datetime
from pathlib import Path
import ipaddress

URLs = {
    "CT": "https://ispip.clang.cn/chinatelecom.txt",
    "CU": "https://ispip.clang.cn/unicom_cnc.txt",
    "CM": "https://ispip.clang.cn/cmcc.txt",
    "CBN": "https://ispip.clang.cn/chinabtn.txt",
    "CERNET": "https://ispip.clang.cn/cernet.txt",
    "GWBN": "https://ispip.clang.cn/gwbn.txt",
    "CNOther": "https://ispip.clang.cn/othernet.txt",
}

IPv6_URLs = {
    "v6_CT": "https://ispip.clang.cn/chinatelecom_ipv6.txt",
    "v6_CU": "https://ispip.clang.cn/unicom_cnc_ipv6.txt",
    "v6_CM": "https://ispip.clang.cn/cmcc_ipv6.txt",
    "v6_CBN": "https://ispip.clang.cn/chinabtn_ipv6.txt",
    "v6_CERNET": "https://ispip.clang.cn/cernet_ipv6.txt",
    "v6_GWBN": "https://ispip.clang.cn/gwbn_ipv6.txt",
    "v6_CNOther": "https://ispip.clang.cn/othernet_ipv6.txt",
}

OUTPUT_FILES = {
    "CT": "fortios_isp_CT.conf.txt",
    "CU": "fortios_isp_CU.conf.txt",
    "CM": "fortios_isp_CM.conf.txt",
    "CBN": "fortios_isp_CBN.conf.txt",
    "CERNET": "fortios_isp_CERNET.conf.txt",
    "GWBN": "fortios_isp_GWBN.conf.txt",
    "CNOther": "fortios_isp_CNOther.conf.txt",
    "v6_CT": "fortios_isp_v6_CT.conf.txt",
    "v6_CU": "fortios_isp_v6_CU.conf.txt",
    "v6_CM": "fortios_isp_v6_CM.conf.txt",
    "v6_CBN": "fortios_isp_v6_CBN.conf.txt",
    "v6_CERNET": "fortios_isp_v6_CERNET.conf.txt",
    "v6_GWBN": "fortios_isp_v6_GWBN.conf.txt",
    "v6_CNOther": "fortios_isp_v6_CNOther.conf.txt",
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

def is_ipv6(ip_string):
    try:
        ipaddress.IPv6Address(ip_string)
        return True
    except:
        return False

def generate_config(isp, lines):
    output = []
    AG = f"zzz_ISPAG_{isp}"
    
    # Determine if IPv6
    is_v6 = is_ipv6(lines[0].split('/')[0]) if lines else False
    
    if is_v6:
        output.append("config firewall address6")
    else:
        output.append("config firewall address")
    
    members = []
    member_bg_map = {}
    
    for index, line in enumerate(lines):
        parts = line.split('/')
        if len(parts) != 2:
            continue
        ip, mask = parts[0], parts[1]
        bg_num = (index // CHUNK_SIZE) + 1
        obj_name = f"zzz_ISP_{isp}_{bg_num}_{ip}_{mask}"
        members.append(obj_name)
        member_bg_map[obj_name] = bg_num
        
        output.append(f'edit "{obj_name}"')
        if is_v6:
            output.append(f'    set ip6 {ip}/{mask}')
        else:
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
        chunk_members = [m for m in members if member_bg_map[m] == g]
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
    all_urls = {**URLs, **IPv6_URLs}
    
    for isp, url in all_urls.items():
        print(f"Fetching {isp} routes...")
        lines = fetch_routes(url)
        if not lines:
            print(f"  No routes found for {isp}")
            continue
        config = generate_config(isp, lines)
        output_filename = OUTPUT_FILES[isp]
        outfile = SCRIPT_DIR / output_filename
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write(config)
        print(f"OK: {outfile} ({len(lines)} routes)")

if __name__ == "__main__":
    main()
