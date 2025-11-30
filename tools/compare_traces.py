import subprocess
import json
import sys
import time

TARGETS = [
    "8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1",
    "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220",
    "4.2.2.1", "4.2.2.2", "142.250.190.46", "142.250.191.206",
    "172.217.164.110", "142.250.184.99", "157.240.229.35", "157.240.195.174",
    "31.13.71.36", "104.244.42.1", "104.244.42.65", "208.80.154.224",
    "98.137.11.163", "74.6.231.20", "205.251.242.103", "54.239.28.85",
    "52.94.233.129", "52.21.160.129", "54.237.226.164", "108.174.10.10",
    "20.112.250.133", "13.107.21.200", "17.253.144.10", "17.253.144.26",
    "151.101.2.167", "151.101.66.167", "151.101.1.140", "151.101.65.140",
    "140.82.112.4", "140.82.113.4", "151.101.1.69", "151.101.65.69"
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

    # Budget trace
    # python3 -m tools.run_budget <target> --method icmp-paris --per-hop-budget 3 --repeats-needed 2 --total-budget 65
    bud_cmd = f"{sys.executable} -m tools.run_budget {target} --method icmp-paris --per-hop-budget 3 --repeats-needed 2 --total-budget 65"
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

if __name__ == "__main__":
    main()
