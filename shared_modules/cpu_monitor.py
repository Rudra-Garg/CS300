import os
import time
import json
import math

# --- Previous state ---
_last_cpu_check_time = None
_last_cpu_usage_value = None
_last_cpu_usage_key = None # To remember if it was ns or usec

def get_cpu_usage():
    """
    Get the CPU usage of the current Docker container.
    
    Returns:
        dict: Dictionary containing CPU usage information
    """
    # CPU usage in nanoseconds
    try:
        # For Docker with cgroups v1
        with open('/sys/fs/cgroup/cpu/cpuacct.usage', 'r') as f:
            cpu_usage_ns = int(f.read().strip())
            return {'cpu_usage_ns': cpu_usage_ns}
    except FileNotFoundError:
        pass
    
    try:
        # For Docker with cgroups v2
        with open('/sys/fs/cgroup/cpu.stat', 'r') as f:
            stats = {}
            for line in f:
                key, value = line.strip().split()
                stats[key] = int(value)
            return stats
    except FileNotFoundError:
        pass
    
    # Try alternative paths for different container runtimes
    cgroup_paths = [
        # Docker with custom cgroup path
        '/sys/fs/cgroup/cpu,cpuacct/cpuacct.usage',
        # Kubernetes
        '/sys/fs/cgroup/cpuacct/cpuacct.usage',
        # Docker Compose with project name
        '/sys/fs/cgroup/cpu/docker/cpuacct.usage',
        # cgroups v2 unified hierarchy
        '/sys/fs/cgroup/cpu.stat',
    ]
    
    for path in cgroup_paths:
        try:
            if path.endswith('cpu.stat'):
                with open(path, 'r') as f:
                    stats = {}
                    for line in f:
                        key, value = line.strip().split()
                        stats[key] = int(value)
                    return stats
            else:
                with open(path, 'r') as f:
                    cpu_usage_ns = int(f.read().strip())
                    return {'cpu_usage_ns': cpu_usage_ns}
        except (FileNotFoundError, IOError):
            continue
    
    raise Exception("Could not find CPU usage information in cgroup filesystem")


def get_cpu_quota():
    """
    Get the CPU quota and period for the container.
    
    Returns:
        dict: Dictionary with CPU quota and period
    """
    quota = -1
    period = 100000  # Default period in microseconds
    
    # Try different cgroup paths
    quota_paths = [
        # cgroups v1
        '/sys/fs/cgroup/cpu/cpu.cfs_quota_us',
        '/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us',
        # cgroups v2
        '/sys/fs/cgroup/cpu.max',
    ]
    
    period_paths = [
        # cgroups v1
        '/sys/fs/cgroup/cpu/cpu.cfs_period_us',
        '/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us',
        # cgroups v2 uses the same cpu.max file for both quota and period
    ]
    
    # Try to get quota
    for path in quota_paths:
        try:
            with open(path, 'r') as f:
                content = f.read().strip()
                # For cgroups v2, the format is "quota period"
                if ' ' in content:
                    quota_val, period_val = content.split()
                    if quota_val != 'max':
                        quota = int(quota_val)
                    period = int(period_val)
                    break
                else:
                    quota = int(content)
                    break
        except (FileNotFoundError, IOError):
            continue
    
    # If we didn't get period from cpu.max, try dedicated period files
    if ' ' not in content and quota != -1:
        for path in period_paths:
            try:
                with open(path, 'r') as f:
                    period = int(f.read().strip())
                    break
            except (FileNotFoundError, IOError):
                continue
    
    return {'cpu_quota_us': quota, 'cpu_period_us': period}


def get_container_cpu_percent_non_blocking():
    """
    Calculate CPU usage percentage since the last call. Non-blocking.

    Returns:
        dict or None: CPU usage info if possible, None if first call or error.
                      Includes 'cpu_percent_normalized' crucial for placement.
    """
    global _last_cpu_check_time, _last_cpu_usage_value, _last_cpu_usage_key

    current_time = time.monotonic() # Use monotonic clock for intervals
    current_usage_info = get_cpu_usage()

    if current_usage_info is None:
        print("WARN: get_cpu_usage() returned None.")
        return None

    # Determine current usage value and key
    current_usage_value = None
    current_usage_key = None
    if 'usage_usec' in current_usage_info:
         current_usage_value = current_usage_info['usage_usec']
         current_usage_key = 'usage_usec'
    elif 'cpu_usage_ns' in current_usage_info:
         current_usage_value = current_usage_info['cpu_usage_ns']
         current_usage_key = 'cpu_usage_ns'
    else:
         print("WARN: Could not determine usage key ('usage_usec' or 'cpu_usage_ns')")
         return None # Cannot calculate

    # --- Check if we have previous data to calculate delta ---
    if _last_cpu_check_time is None or _last_cpu_usage_value is None or _last_cpu_usage_key is None:
        print("INFO: First CPU usage reading, cannot calculate percentage yet.")
        # Store current state for the *next* call
        _last_cpu_check_time = current_time
        _last_cpu_usage_value = current_usage_value
        _last_cpu_usage_key = current_usage_key
        return None # Cannot calculate percentage on first run

    # --- Calculate delta ---
    time_delta_sec = current_time - _last_cpu_check_time
    usage_delta = current_usage_value - _last_cpu_usage_value

    # Convert previous/current usage to nanoseconds for consistent calculation
    usage_delta_ns = 0
    if current_usage_key == 'usage_usec' and _last_cpu_usage_key == 'usage_usec':
        usage_delta_ns = usage_delta * 1000
    elif current_usage_key == 'cpu_usage_ns' and _last_cpu_usage_key == 'cpu_usage_ns':
        usage_delta_ns = usage_delta
    else:
        # Handle potential unit mismatch between readings (unlikely but possible)
        print(f"WARN: CPU usage unit mismatch between readings ({_last_cpu_usage_key} -> {current_usage_key}). Recalculating on next cycle.")
        # Reset and wait for next cycle
        _last_cpu_check_time = current_time
        _last_cpu_usage_value = current_usage_value
        _last_cpu_usage_key = current_usage_key
        return None


    # Store current state for the *next* call BEFORE returning
    _last_cpu_check_time = current_time
    _last_cpu_usage_value = current_usage_value
    _last_cpu_usage_key = current_usage_key


    # --- Percentage Calculation ---
    if time_delta_sec <= 0:
         print("WARN: Time delta is zero or negative, cannot calculate CPU percent.")
         return None # Avoid division by zero

    time_delta_ns = time_delta_sec * 1_000_000_000

    # Raw percentage relative to one core
    cpu_percent_raw = (usage_delta_ns / time_delta_ns) * 100

    # Get quota info
    quota_info = get_cpu_quota()
    cpu_quota_us = quota_info.get('cpu_quota_us', -1)
    cpu_period_us = quota_info.get('cpu_period_us', 100000)

    cpu_percent_normalized = math.nan # Default to NaN if no quota
    num_cores_allocated = math.nan

    # Calculate normalized percentage if quota is set
    if cpu_quota_us > 0 and cpu_period_us > 0:
        num_cores_allocated = cpu_quota_us / cpu_period_us
        if num_cores_allocated > 0:
            cpu_percent_normalized = cpu_percent_raw / num_cores_allocated
            # Clamp between 0 and 100
            cpu_percent_normalized = max(0.0, min(100.0, cpu_percent_normalized))
        else:
            print("WARN: Calculated zero allocated cores based on quota/period.")
    else:
        print("INFO: No CPU quota set (-1 or max), normalized percentage not applicable.")


    return {
        'cpu_percent_raw': max(0.0, cpu_percent_raw), # Percentage relative to 1 core (can be > 100)
        'cpu_percent_normalized': cpu_percent_normalized, # Percentage relative to quota (0-100 or NaN)
        'num_cores_allocated': num_cores_allocated, # Effective cores from quota (or NaN)
        'interval_sec': time_delta_sec
    }

def monitor_container_cpu(interval=1.0, count=10):
    print(f"Monitoring container CPU usage (non-blocking) approx every {interval}s intervals:")
    print("Timestamp".ljust(25), "Norm %".rjust(8), "Raw %".rjust(8), "Cores".rjust(6))
    print("-" * 50)

    # Initial call to prime the _last values
    get_container_cpu_percent_non_blocking()
    time.sleep(interval) # Initial wait

    for _ in range(count):
        start_call = time.monotonic()
        cpu_info = get_container_cpu_percent_non_blocking()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if cpu_info:
             norm_str = f"{cpu_info['cpu_percent_normalized']:7.2f}%" if not math.isnan(cpu_info['cpu_percent_normalized']) else "  N/A  "
             raw_str = f"{cpu_info['cpu_percent_raw']:7.2f}%"
             cores_str = f"{cpu_info['num_cores_allocated']:5.2f}" if not math.isnan(cpu_info['num_cores_allocated']) else " N/A "
             print(f"{timestamp}  {norm_str} {raw_str} {cores_str}")
        else:
            print(f"{timestamp}  {'Waiting'.rjust(8)} {' '.rjust(8)} {' '.rjust(6)}")

        # Wait for the remainder of the interval
        elapsed = time.monotonic() - start_call
        wait_time = interval - elapsed
        if wait_time > 0:
            time.sleep(wait_time)


if __name__ == "__main__":
    print("Container CPU Usage Monitor")
    print("==========================")
    try:
        monitor_container_cpu(interval=2.0, count=5)
    except Exception as e:
        print(f"Error: {e}")
        print("\nFallback to cgroup filesystem inspection:")
        
        # Try to list available cgroup files as a fallback
        cgroup_dirs = [
            '/sys/fs/cgroup',
            '/sys/fs/cgroup/cpu',
            '/sys/fs/cgroup/cpuacct',
            '/sys/fs/cgroup/cpu,cpuacct'
        ]
        
        for directory in cgroup_dirs:
            if os.path.exists(directory):
                print(f"\nContents of {directory}:")
                try:
                    print(os.listdir(directory))
                except:
                    print("Cannot access directory")
