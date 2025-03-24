import os
import json
import time
import logging
import threading
import psutil
import requests
from flask import Flask, jsonify, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fog_node.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class FogNode:
    def __init__(self):
        # Read environment variables
        self.node_type = os.environ.get('NODE_TYPE', 'EDGE')
        self.node_id = os.environ.get('NODE_ID', '1')
        self.placement_strategy = os.environ.get('PLACEMENT_STRATEGY', 'GVMP')
        self.config_name = os.environ.get('CONFIG_NAME', 'Config-1')
        
        # Parent node connection info
        self.parent_host = os.environ.get('PARENT_HOST', None)
        self.parent_port = os.environ.get('PARENT_PORT', None)
        
        # Node resources
        self.resources = {
            'cpu_cores': psutil.cpu_count(),
            'cpu_percent': 0,
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_total': psutil.disk_usage('/').total,
            'disk_available': psutil.disk_usage('/').free
        }
        
        # Running modules
        self.modules = {}
        
        # Load configuration
        self.config = self.load_config()
        
        # Initialize node based on type and strategy
        self.initialize_node()
        
        # Start resource monitoring
        self.start_monitoring()
        
        logger.info(f"Initialized {self.node_type} node (ID: {self.node_id}) with strategy: {self.placement_strategy}")

    def load_config(self):
        """Load configuration from file"""
        config_path = f"config/{self.config_name}.json"
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Return default configuration
            return {
                "numOfDepts": 2,
                "numOfMobilesPerDept": 5,
                "applicationModules": [
                    {"name": "client", "requiredCpu": 10, "requiredMemory": 100},
                    {"name": "concentration_calculator", "requiredCpu": 10, "requiredMemory": 200},
                    {"name": "connector", "requiredCpu": 10, "requiredMemory": 150}
                ]
            }

    def initialize_node(self):
        """Initialize node based on type and placement strategy"""
        if self.node_type == "CLOUD":
            self.initialize_cloud()
        elif self.node_type == "PROXY":
            self.initialize_proxy()
        elif self.node_type == "EDGE":
            self.initialize_edge()
        else:
            logger.warning(f"Unknown node type: {self.node_type}")

    def initialize_cloud(self):
        """Initialize cloud node"""
        logger.info("Initializing as Cloud node")
        
        # If using CLOUD placement strategy, initialize all modules
        if self.placement_strategy == "CLOUD":
            for module in self.config["applicationModules"]:
                self.start_module(module["name"])

    def initialize_proxy(self):
        """Initialize proxy node"""
        logger.info("Initializing as Proxy node")
        
        # If using EDGE placement strategy, initialize some modules
        if self.placement_strategy == "EDGE":
            # In EDGE strategy, concentration_calculator runs on proxy
            self.start_module("concentration_calculator")

    def initialize_edge(self):
        """Initialize edge node"""
        logger.info(f"Initializing as Edge node with ID: {self.node_id}")
        
        # Always start client module on edge nodes
        self.start_module("client")
        
        # If using GVMP strategy, determine other modules to run
        if self.placement_strategy == "GVMP":
            # In GVMP, modules are placed based on resources and location
            # For this example, we'll place connector on some edge nodes
            if int(self.node_id) % 2 == 0:  # Even-numbered nodes
                self.start_module("connector")

    def start_module(self, module_name):
        """Start a module on this node"""
        if module_name in self.modules:
            logger.warning(f"Module {module_name} is already running")
            return
        
        # Find module configuration
        module_config = next((m for m in self.config["applicationModules"] if m["name"] == module_name), None)
        if not module_config:
            logger.warning(f"Module {module_name} not found in configuration")
            return
        
        # Create module instance
        self.modules[module_name] = {
            "name": module_name,
            "status": "running",
            "started_at": time.time(),
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "config": module_config
        }
        
        # Start module in a separate thread
        threading.Thread(target=self.run_module, args=(module_name,), daemon=True).start()
        
        logger.info(f"Started module: {module_name}")

    def run_module(self, module_name):
        """Simulate module execution"""
        module = self.modules.get(module_name)
        if not module:
            return
        
        try:
            while module["status"] == "running":
                # Simulate CPU and memory usage
                module["cpu_usage"] = 0.5 + 0.5 * (time.time() % 10) / 10  # 50-100% CPU usage
                module["memory_usage"] = module["config"]["requiredMemory"] * (0.7 + 0.3 * (time.time() % 10) / 10)  # 70-100% memory usage
                
                # Simulate data processing
                if module_name == "client":
                    # Client module sends data to concentration_calculator
                    self.send_data(module_name, "concentration_calculator", {"type": "sensor_data", "value": time.time()})
                
                elif module_name == "concentration_calculator":
                    # Concentration calculator processes data and sends to connector
                    self.send_data(module_name, "connector", {"type": "processed_data", "value": time.time()})
                
                elif module_name == "connector":
                    # Connector sends data back to client
                    self.send_data(module_name, "client", {"type": "global_state", "value": time.time()})
                
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in module {module_name}: {e}")
            module["status"] = "error"

    def send_data(self, source, destination, data):
        """Send data from one module to another"""
        # If destination module is running locally, process directly
        if destination in self.modules:
            logger.debug(f"Local data transfer: {source} -> {destination}")
            # Process data locally
            return
        
        # Otherwise, try to send to parent node
        if self.parent_host and self.parent_port:
            try:
                url = f"http://{self.parent_host}:{self.parent_port}/data"
                payload = {
                    "source": source,
                    "destination": destination,
                    "data": data,
                    "node_id": self.node_id,
                    "node_type": self.node_type
                }
                requests.post(url, json=payload, timeout=1)
                logger.debug(f"Sent data to parent: {source} -> {destination}")
            except Exception as e:
                logger.error(f"Error sending data to parent: {e}")

    def stop_module(self, module_name):
        """Stop a module"""
        if module_name in self.modules:
            self.modules[module_name]["status"] = "stopped"
            logger.info(f"Stopped module: {module_name}")

    def start_monitoring(self):
        """Start resource monitoring thread"""
        def monitor_resources():
            while True:
                self.resources["cpu_percent"] = psutil.cpu_percent(interval=1)
                self.resources["memory_available"] = psutil.virtual_memory().available
                self.resources["disk_available"] = psutil.disk_usage('/').free
                time.sleep(5)
        
        threading.Thread(target=monitor_resources, daemon=True).start()

# Create fog node instance
fog_node = FogNode()

@app.route('/status', methods=['GET'])
def get_status():
    """Get node status"""
    return jsonify({
        "node_type": fog_node.node_type,
        "node_id": fog_node.node_id,
        "placement_strategy": fog_node.placement_strategy,
        "resources": fog_node.resources,
        "modules": len(fog_node.modules)
    })

@app.route('/modules', methods=['GET'])
def get_modules():
    """Get running modules"""
    return jsonify({
        "modules": list(fog_node.modules.values())
    })

@app.route('/modules/<module_name>', methods=['POST'])
def start_module_api(module_name):
    """Start a module"""
    fog_node.start_module(module_name)
    return jsonify({"status": "success", "message": f"Started module {module_name}"})

@app.route('/modules/<module_name>', methods=['DELETE'])
def stop_module_api(module_name):
    """Stop a module"""
    fog_node.stop_module(module_name)
    return jsonify({"status": "success", "message": f"Stopped module {module_name}"})

@app.route('/data', methods=['POST'])
def receive_data():
    """Receive data from other nodes"""
    data = request.json
    source = data.get("source")
    destination = data.get("destination")
    
    logger.debug(f"Received data: {source} -> {destination}")
    
    # If destination module is running locally, process it
    if destination in fog_node.modules:
        # Process data locally
        return jsonify({"status": "success", "message": "Data processed locally"})
    
    # Otherwise, forward to parent node if we're not the cloud
    if fog_node.node_type != "CLOUD" and fog_node.parent_host and fog_node.parent_port:
        try:
            url = f"http://{fog_node.parent_host}:{fog_node.parent_port}/data"
            requests.post(url, json=data, timeout=1)
            return jsonify({"status": "success", "message": "Data forwarded to parent"})
        except Exception as e:
            logger.error(f"Error forwarding data: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return jsonify({"status": "error", "message": "Cannot process or forward data"}), 400

if __name__ == '__main__':
    # Get port from environment or use default based on node type
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)