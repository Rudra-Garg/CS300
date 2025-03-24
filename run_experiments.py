import os
import subprocess
import time
import matplotlib.pyplot as plt
import requests
import json
from datetime import datetime

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
        for node, port in [("cloud", 8080), ("proxy", 8081), ("edge1", 8082), ("edge2", 8083)]:
            try:
                # Get status
                status_resp = requests.get(f"http://localhost:{port}/status", timeout=1)
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    metrics[node]["cpu"].append(status_data["resources"]["cpu_percent"])
                    metrics[node]["memory"].append(status_data["resources"]["memory_available"])
                
                # Get modules
                modules_resp = requests.get(f"http://localhost:{port}/modules", timeout=1)
                if modules_resp.status_code == 200:
                    modules_data = modules_resp.json()
                    metrics[node]["modules"].append(len(modules_data["modules"]))
            except Exception as e:
                print(f"Error collecting metrics from {node}: {e}")
        
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
        ax.plot(metrics[node]["cpu"], label=node)
    ax.set_title(f"CPU Usage - {strategy} - {config}")
    ax.set_xlabel("Time (5s intervals)")
    ax.set_ylabel("CPU %")
    ax.legend()
    
    # Plot memory usage
    ax = axs[0, 1]
    for node in metrics:
        ax.plot(metrics[node]["memory"], label=node)
    ax.set_title(f"Memory Available - {strategy} - {config}")
    ax.set_xlabel("Time (5s intervals)")
    ax.set_ylabel("Memory (bytes)")
    ax.legend()
    
    # Plot module count
    ax = axs[1, 0]
    for node in metrics:
        ax.plot(metrics[node]["modules"], label=node)
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
            results[config][strategy] = metrics
            plot_results(metrics, strategy, config)
    
    print("\nAll experiments completed!")

if __name__ == "__main__":
    main()