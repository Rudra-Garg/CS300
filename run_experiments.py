import os
import subprocess
import time
import matplotlib.pyplot as plt
import requests
import json
from datetime import datetime
import socket

def get_container_ips():
    """Get IP addresses of running containers"""
    container_ips = {}
    try:
        # Get container names and their IPs
        cmd = "docker inspect -f '{{.Name}}|{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $(docker ps -q)"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        
        for line in output.split('\n'):
            if '|' in line:
                name, ip = line.split('|')
                # Remove leading slash from container name
                name = name.lstrip('/')
                # Extract base name (without numbers)
                base_name = name.split('-')[0] if '-' in name else name
                container_ips[base_name] = ip
        
        print(f"Container IPs: {container_ips}")
        return container_ips
    except Exception as e:
        print(f"Error getting container IPs: {e}")
        return {}

def validate_containers_running():
    """Validate that all required containers are running"""
    required_containers = ["cloud", "proxy", "edge1", "edge2"]
    running_containers = []
    
    try:
        output = subprocess.check_output("docker ps --format '{{.Names}}'", shell=True).decode().strip()
        running_containers = output.split('\n')
        
        # Check if all required containers are running
        missing = []
        for container in required_containers:
            found = False
            for running in running_containers:
                if container in running:
                    found = True
                    break
            if not found:
                missing.append(container)
        
        if missing:
            print(f"Warning: The following containers are not running: {missing}")
            return False
        
        print("All required containers are running")
        return True
    except Exception as e:
        print(f"Error validating containers: {e}")
        return False

def run_experiment(strategy, config, duration=60):
    """Run an experiment with the specified strategy and configuration"""
    print(f"Running experiment with strategy: {strategy}, config: {config}")
    
    # Set environment variables
    os.environ["PLACEMENT_STRATEGY"] = strategy
    os.environ["CONFIG_NAME"] = config
    
    # Start the containers
    subprocess.run(["docker-compose", "up", "-d"])
    
    # Wait for containers to initialize
    print("Waiting for containers to initialize...")
    time.sleep(10)
    
    # Validate containers are running
    if not validate_containers_running():
        print("Error: Not all required containers are running. Aborting experiment.")
        subprocess.run(["docker-compose", "down"])
        return None
    
    # Get container IPs
    container_ips = get_container_ips()
    if not container_ips:
        print("Error: Could not get container IPs. Aborting experiment.")
        subprocess.run(["docker-compose", "down"])
        return None
    
    # Map container names to their IPs and ports
    node_endpoints = {
        "cloud": (container_ips.get("cloud", "localhost"), 8080),
        "proxy": (container_ips.get("proxy", "localhost"), 8080),
        "edge1": (container_ips.get("edge1", "localhost"), 8080),
        "edge2": (container_ips.get("edge2", "localhost"), 8080)
    }
    
    # Collect metrics over time
    metrics = {
        "cloud": {"cpu": [], "memory": [], "modules": []},
        "proxy": {"cpu": [], "memory": [], "modules": []},
        "edge1": {"cpu": [], "memory": [], "modules": []},
        "edge2": {"cpu": [], "memory": [], "modules": []}
    }
    
    start_time = time.time()
    while time.time() - start_time < duration:
        # Collect metrics from each node
        for node, (host, port) in node_endpoints.items():
            try:
                # Get status
                status_resp = requests.get(f"http://{host}:{port}/status", timeout=2)
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    metrics[node]["cpu"].append(status_data["resources"]["cpu_percent"])
                    metrics[node]["memory"].append(status_data["resources"]["memory_available"])
                
                # Get modules
                modules_resp = requests.get(f"http://{host}:{port}/modules", timeout=2)
                if modules_resp.status_code == 200:
                    modules_data = modules_resp.json()
                    metrics[node]["modules"].append(len(modules_data["modules"]))
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error for {node} at {host}:{port}: {e}")
                # Add None values to maintain data alignment
                metrics[node]["cpu"].append(None)
                metrics[node]["memory"].append(None)
                metrics[node]["modules"].append(None)
            except Exception as e:
                print(f"Error collecting metrics from {node} at {host}:{port}: {e}")
                # Add None values to maintain data alignment
                metrics[node]["cpu"].append(None)
                metrics[node]["memory"].append(None)
                metrics[node]["modules"].append(None)
        
        time.sleep(5)
    
    # Stop the containers
    subprocess.run(["docker-compose", "down"])
    
    # Save metrics to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"results_{strategy}_{config}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"Experiment completed. Results saved to {filename}")
    return metrics

def plot_results(metrics, strategy, config):
    """Plot the results of an experiment"""
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    
    # Plot CPU usage
    ax = axs[0, 0]
    for node in metrics:
        # Filter out None values
        data_points = [(i, cpu) for i, cpu in enumerate(metrics[node]["cpu"]) if cpu is not None]
        if data_points:
            indices, values = zip(*data_points)
            ax.plot(indices, values, label=node)
    ax.set_title(f"CPU Usage - {strategy} - {config}")
    ax.set_xlabel("Time (5s intervals)")
    ax.set_ylabel("CPU %")
    ax.legend()
    
    # Plot memory usage
    ax = axs[0, 1]
    for node in metrics:
        # Filter out None values
        data_points = [(i, mem) for i, mem in enumerate(metrics[node]["memory"]) if mem is not None]
        if data_points:
            indices, values = zip(*data_points)
            ax.plot(indices, values, label=node)
    ax.set_title(f"Memory Available - {strategy} - {config}")
    ax.set_xlabel("Time (5s intervals)")
    ax.set_ylabel("Memory (bytes)")
    ax.legend()
    
    # Plot module count
    ax = axs[1, 0]
    for node in metrics:
        # Filter out None values
        data_points = [(i, mod) for i, mod in enumerate(metrics[node]["modules"]) if mod is not None]
        if data_points:
            indices, values = zip(*data_points)
            ax.plot(indices, values, label=node)
    ax.set_title(f"Module Count - {strategy} - {config}")
    ax.set_xlabel("Time (5s intervals)")
    ax.set_ylabel("Number of Modules")
    ax.legend()
    
    # Save the plot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"plot_{strategy}_{config}_{timestamp}.png"
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Plot saved to {filename}")

def main():
    """Run experiments with different strategies and configurations"""
    strategies = ["CLOUD", "EDGE", "GVMP"]
    configs = ["Config-1"]
    
    results = {}
    
    for config in configs:
        results[config] = {}
        for strategy in strategies:
            print(f"\n=== Running {strategy} strategy with {config} ===\n")
            metrics = run_experiment(strategy, config)
            if metrics:
                results[config][strategy] = metrics
                plot_results(metrics, strategy, config)
            else:
                print(f"Skipping results for {strategy} with {config} due to errors")
    
    print("\nAll experiments completed!")

if __name__ == "__main__":
    main()