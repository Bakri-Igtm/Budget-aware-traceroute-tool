import subprocess
import json
import sys
import time

TARGETS = [
    # Google DNS
    "8.8.8.8", "8.8.4.4",
    # Cloudflare DNS
    "1.1.1.1", "1.0.0.1",
    # Quad9 DNS
    "9.9.9.9", "149.112.112.112",
    # OpenDNS
    "208.67.222.222", "208.67.220.220",
    # Level3 DNS
    "4.2.2.1", "4.2.2.2",
    # Google Web
    "142.250.190.46", "142.250.191.206", "172.217.164.110", "142.250.184.99",
    # Meta / Facebook
    "157.240.229.35", "157.240.195.174", "31.13.71.36",
    # X / Twitter
    "104.244.42.1", "104.244.42.65",
    # Wikipedia
    "208.80.154.224",
    # Yahoo
    "98.137.11.163", "74.6.231.20",
    # Amazon / AWS
    "205.251.242.103", "54.239.28.85", "52.94.233.129", "52.21.160.129", "54.237.226.164",
    # LinkedIn
    "108.174.10.10",
    # Microsoft / Azure
    "20.112.250.133", "13.107.21.200",
    # Apple
    "17.253.144.10", "17.253.144.26",
    # Reddit (Fastly)
    "151.101.2.167", "151.101.66.167",
    # Stack Overflow (Fastly)
    "151.101.1.140", "151.101.65.140",
    # GitHub
    "140.82.112.4", "140.82.113.4",
    # Imgur (Fastly)
    "151.101.1.69", "151.101.65.69",
    # --- Additional targets (to reach 100) ---
    # Comodo DNS
    "8.26.56.26", "8.20.247.20",
    # Neustar UltraDNS
    "64.6.64.6", "64.6.65.6", "156.154.70.1", "156.154.71.1",
    # CleanBrowsing DNS
    "185.228.168.9", "185.228.169.9",
    # AdGuard DNS
    "94.140.14.14", "94.140.15.15",
    # Yandex DNS
    "77.88.8.8", "77.88.8.1",
    # Google (additional)
    "216.58.214.206", "172.217.14.99", "142.251.33.78", "142.251.40.174", "216.239.32.21",
    # Meta / Facebook (additional)
    "185.60.216.35", "157.240.1.35",
    # Akamai CDN
    "23.192.228.80", "23.45.229.117", "23.4.43.67",
    # Cloudflare CDN
    "104.16.132.229", "104.18.32.7",
    # Fastly CDN (additional)
    "151.101.129.69", "151.101.193.140", "199.232.68.133",
    # Edgecast / Verizon CDN
    "152.199.19.161",
    # IANA example.com
    "93.184.216.34",
    # AWS CloudFront
    "52.85.151.49", "13.227.219.76", "99.86.230.81",
    # AWS Global Accelerator
    "3.33.152.147", "15.197.142.173",
    # GCP
    "35.186.224.25", "34.107.243.93", "35.190.247.0",
    # Microsoft / Azure (additional)
    "204.79.197.200", "13.107.42.14", "40.90.4.1",
    "20.53.203.50", "20.190.151.70", "20.190.151.132",
    # Dropbox
    "162.125.1.1", "162.125.66.1",
]

def run_command(cmd):
    try:
        # Run and capture stdout
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        # print(f"Error running command: {cmd}\n{e}", file=sys.stderr)
        return None

def compare(target):
    # Regular trace
    # python3 -m tools.regular_trace <target> 3 icmp-paris
    reg_cmd = f"{sys.executable} -m tools.regular_trace {target} 3 icmp-paris"
    reg_data = run_command(reg_cmd)

    if not reg_data:
        return None

    # Use the regular trace's last probed TTL as the max-ttl for budget trace
    # so it doesn't waste time probing beyond where the regular trace stopped (e.g. gaplimit)
    max_ttl = reg_data.get("last_ttl_probed", 32)

    # Budget trace
    # python3 -m tools.run_budget <target> --method icmp-paris --per-hop-budget 3 --repeats-needed 2 --total-budget 65 --max-ttl <max_ttl>
    bud_cmd = f"{sys.executable} -m tools.run_budget {target} --method icmp-paris --per-hop-budget 3 --repeats-needed 2 --total-budget 65 --max-ttl {max_ttl}"
    bud_data = run_command(bud_cmd)

    if not reg_data or not bud_data:
        return None

    # Calculate metrics
    reg_path = reg_data.get("path", {})
    bud_path = bud_data.get("path", {})
    
    # Convert keys to int
    reg_path = {int(k): v for k, v in reg_path.items()}
    bud_path = {int(k): v for k, v in bud_path.items()}

    # Accuracy: Matches on non-empty regular hops
    matches = 0
    total_comparable = 0
    
    # We iterate over the hops found in regular trace
    for ttl, ip in reg_path.items():
        if ip and ip != "∅":
            total_comparable += 1
            if bud_path.get(ttl) == ip:
                matches += 1
    
    accuracy = (matches / total_comparable * 100) if total_comparable > 0 else 0.0
    
    reg_probes = reg_data.get("probes_used_est", 0)
    bud_probes = bud_data.get("probes_used", 0)
    
    return {
        "target": target,
        "accuracy": accuracy,
        "reg_probes": reg_probes,
        "bud_probes": bud_probes
    }

def main():
    results = []
    print(f"{'Target':<30} | {'Acc %':<10} | {'Reg Probes':<12} | {'Bud Probes':<12}")
    print("-" * 75)
    
    for t in TARGETS:
        res = compare(t)
        if res:
            print(f"{res['target']:<30} | {res['accuracy']:6.2f}%    | {res['reg_probes']:<12} | {res['bud_probes']:<12}")
            results.append(res)
        else:
            print(f"{t:<30} | FAILED")

    # Filter out results where budget probes > regular probes
    valid_results = [r for r in results if r['bud_probes'] <= r['reg_probes']]
    excluded_count = len(results) - len(valid_results)

    # Summary
    if valid_results:
        avg_acc = sum(r['accuracy'] for r in valid_results) / len(valid_results)
        total_reg = sum(r['reg_probes'] for r in valid_results)
        total_bud = sum(r['bud_probes'] for r in valid_results)
        reduction = ((total_reg - total_bud) / total_reg * 100) if total_reg > 0 else 0
        
        print("-" * 75)
        print(f"Total Targets (Attempted): {len(results)}")
        print(f"Excluded (Bud > Reg): {excluded_count}")
        print(f"Valid Targets: {len(valid_results)}")
        print(f"Average Accuracy (Valid): {avg_acc:.2f}%")
        print(f"Total Probes (Regular, Valid): {total_reg}")
        print(f"Total Probes (Budget, Valid):  {total_bud}")
        print(f"Probe Reduction (Valid): {reduction:.2f}%")
    else:
        print("-" * 75)
        print("No valid results found (all failed or budget > regular).")

    # Write results to a JSON file with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"compare_results_{timestamp}.json"
    output = {
        "timestamp": datetime.now().isoformat(),
        "total_attempted": len(results),
        "excluded_count": excluded_count,
        "valid_count": len(valid_results),
        "summary": {
            "avg_accuracy": round(avg_acc, 2) if valid_results else None,
            "total_reg_probes": total_reg if valid_results else None,
            "total_bud_probes": total_bud if valid_results else None,
            "probe_reduction_pct": round(reduction, 2) if valid_results else None,
        },
        "results": results,
    }
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {output_file}")

if __name__ == "__main__":
    main()
