#!/usr/bin/env python3
import requests
from datetime import datetime
from pathlib import Path
import os
import ipaddress


# 工作目录 = workflow 的 working-directory (.github/temp)
WORKDIR = Path.cwd()

# 缓存目录 = 工作目录
TEMP_DIR = WORKDIR
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 输出目录 = 工作目录/output
OUTPUT_DIR = WORKDIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ================================
# Data sources (gaoyifan)
# ================================
URLs = {
    "CT": "https://gaoyifan.github.io/china-operator-ip/chinanet.txt",
    "CU": "https://gaoyifan.github.io/china-operator-ip/unicom.txt",
    "CM": "https://gaoyifan.github.io/china-operator-ip/cmcc.txt",
    "CERNET": "https://gaoyifan.github.io/china-operator-ip/cernet.txt",
    "CSTNET": "https://gaoyifan.github.io/china-operator-ip/cstnet.txt",
    "DRPENG": "https://gaoyifan.github.io/china-operator-ip/drpeng.txt",
    "GOOGLECN": "https://gaoyifan.github.io/china-operator-ip/googlecn.txt",
}

IPv6_URLs = {
    "v6_CT": "https://gaoyifan.github.io/china-operator-ip/chinanet6.txt",
    "v6_CU": "https://gaoyifan.github.io/china-operator-ip/unicom6.txt",
    "v6_CM": "https://gaoyifan.github.io/china-operator-ip/cmcc6.txt",
    "v6_CERNET": "https://gaoyifan.github.io/china-operator-ip/cernet6.txt",
    "v6_CSTNET": "https://gaoyifan.github.io/china-operator-ip/cstnet6.txt",
    "v6_DRPENG": "https://gaoyifan.github.io/china-operator-ip/drpeng6.txt",
    "v6_GOOGLECN": "https://gaoyifan.github.io/china-operator-ip/googlecn6.txt",
}

# ================================
# Output filenames
# ================================
OUTPUT_FILES = {isp: f"fortios_isp_{isp}.conf.txt" for isp in URLs}
OUTPUT_FILES.update({isp: f"fortios_isp_{isp}.conf.txt" for isp in IPv6_URLs})

# ================================
# Constants
# ================================
CHUNK_SIZE = 600
TODAY = datetime.now().strftime("%Y-%m-%d")


# ================================
# Fetch raw text
# ================================
def fetch_raw(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

# ================================
# Detect IPv6
# ================================
def is_ipv6(ip_string):
    try:
        ipaddress.IPv6Address(ip_string)
        return True
    except:
        return False

# ================================
# Diff detection
# ================================
def has_changed(isp, new_content):
    temp_file = TEMP_DIR / f"{isp}.txt"
    if temp_file.exists():
        old_content = temp_file.read_text(encoding="utf-8")
        if old_content == new_content:
            return False
    temp_file.write_text(new_content, encoding="utf-8")
    return True

# ================================
# Generate FortiOS config
# ================================
def generate_config(isp, lines):
    output = []
    AG = f"zzz_ISPAG_{isp}"

    # Determine IPv6
    is_v6 = is_ipv6(lines[0].split('/')[0]) if lines else False

    if is_v6:
        output.append("config firewall address6")
    else:
        output.append("config firewall address")

    members = []
    member_bg_map = {}

    # Address objects
    for index, line in enumerate(lines):
        ip, mask = line.split('/')
        bg_num = (index // CHUNK_SIZE) + 1
        obj_name = f"zzz_ISP_{isp}_{bg_num}_{ip}_{mask}"

        members.append(obj_name)
        member_bg_map[obj_name] = bg_num

        output.append(f'edit "{obj_name}"')
        if is_v6:
            output.append(f'    set ip6 {ip}/{mask}')
        else:
            output.append(f'    set subnet {ip}/{mask}')
        output.append("    set allow-routing enable")
        output.append(f'    set comment "update-date: {TODAY}"')
        output.append("next")

    output.append("end\n")

    # BG groups
    bg_count = (len(lines) + CHUNK_SIZE - 1) // CHUNK_SIZE
    bg_list = []

    for g in range(1, bg_count + 1):
        bg_name = f"zzz_ISPBG_{isp}_{g}"
        bg_list.append(bg_name)

        chunk_members = [m for m in members if member_bg_map[m] == g]
        if not chunk_members:
            continue

        output.append("config firewall addrgrp")
        output.append(f'    edit "{bg_name}"')
        output.append("        unset member")
        output.append("        set member " + " ".join(f'"{m}"' for m in chunk_members))
        output.append("        set allow-routing enable")
        output.append("    next")
        output.append("end\n")

    # AG group
    output.append("config firewall addrgrp")
    output.append(f'    edit "{AG}"')
    output.append("        unset member")
    output.append("        set member " + " ".join(f'"{bg}"' for bg in bg_list))
    output.append("        set allow-routing enable")
    output.append("    next")
    output.append("end\n")

    return "\n".join(output)

# ================================
# Main
# ================================
def main():
    all_urls = {**URLs, **IPv6_URLs}

    for isp, url in all_urls.items():
        print(f"Fetching {isp}...")

        raw_text = fetch_raw(url)
        if not raw_text:
            print(f"  Failed: {isp}")
            continue

        # Diff check
        if not has_changed(isp, raw_text):
            print(f"  No change for {isp}, skip.")
            continue

        # Parse CIDR lines
        lines = [line.strip() for line in raw_text.split("\n") if "/" in line]

        config = generate_config(isp, lines)
        outfile = OUTPUT_DIR / OUTPUT_FILES[isp]
        outfile.write_text(config, encoding="utf-8")

        print(f"  UPDATED: {outfile} ({len(lines)} routes)")

if __name__ == "__main__":
    main()
