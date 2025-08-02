

# **Performance Evaluation of Fog Computing Module Placement Strategies (GVMP vs. EWMP) using a Docker-based Virtual Testbed**

## **1.0 Project Overview**

### **1.1 Introduction**

The rapid proliferation of Internet of Things (IoT) devices, projected to reach one trillion connected devices by 2025, is generating an unprecedented volume of data.1 While traditional cloud computing offers vast computational and storage resources, its centralized nature introduces significant challenges for many modern IoT applications, primarily high network latency and bandwidth congestion.1 These limitations are particularly detrimental to real-time, latency-sensitive applications such as autonomous vehicles, industrial automation, and augmented reality gaming.1

Fog computing has emerged as a compelling paradigm to address these challenges. By extending cloud services and computation closer to the network edge—utilizing resources on intermediate devices like gateways, routers, and edge servers—Fog computing aims to reduce latency, decrease network traffic, and enhance responsiveness.1 However, the effectiveness of a Fog architecture critically depends on the strategy used to place application components, or "modules," onto the available heterogeneous devices. This module placement problem is known to be NP-Hard, making the development of efficient heuristics essential.1

This project presents a comprehensive framework for the comparative performance evaluation of IoT application module placement strategies. It specifically introduces and evaluates a novel, sibling-aware strategy named **Gateway Validation Module Placement (GVMP)** against the established **Edge-Ward Module Placement (EWMP)** heuristic and a traditional **Cloud-Only** baseline.1 The evaluation is conducted through a dual-methodology approach: quantitative analysis using the iFogSim simulation toolkit and practical validation using the Docker-based virtual testbed detailed in this document.1

### **1.2 Primary Objectives**

The central objective of this project is to design, implement, and conduct a rigorous comparative performance evaluation of the GVMP strategy against the baseline EWMP strategy within a heterogeneous Fog computing environment. The primary goals are to assess the effectiveness of GVMP in minimizing end-to-end application latency and reducing overall network usage.1

Specifically, this project and the accompanying software artifact aim to:

1. Define and contrast the algorithmic logic of EWMP and GVMP, with a particular focus on GVMP's innovative sibling fog device resource validation mechanism.1  
2. Implement both strategies within the iFogSim simulation toolkit for quantitative analysis of latency and network usage under various configurations.1  
3. Develop and deploy a practical, observable, and reproducible **virtual testbed environment** using Docker containers, network emulation tools, and a comprehensive monitoring stack (Prometheus/Grafana).1 This README primarily focuses on this testbed.  
4. Utilize the virtual testbed to validate and compare the real-world performance characteristics (end-to-end latency, CPU utilization) of applications deployed according to different placement configurations that emulate the outcomes of these strategies.1  
5. Analyze and interpret the results from both simulation and virtual emulation to provide a comprehensive assessment of the relative strengths and weaknesses of the GVMP strategy compared to EWMP.1

A crucial aspect of this repository's virtual testbed is its role as a practical validation tool. The project's core algorithmic innovations, EWMP and GVMP, were implemented and tested within the iFogSim simulation environment as described in the main research report.1 The Docker-based testbed provided here does not contain a runtime implementation of these dynamic placement algorithms. Instead, it provides a powerful environment to

**emulate the outcomes** of such placement decisions. This is achieved by manually configuring where application modules are executed via environment variables (\*\_PROCESSING\_LEVEL).1 For example, setting the gateway to perform all processing steps simulates a scenario where a strategy like GVMP has successfully placed all modules on an edge device. This approach allows users to observe and measure the tangible performance impact (latency, CPU load, network traffic patterns) of different placement configurations under more realistic conditions that include operating system overhead, network stack behavior, and resource contention, thereby corroborating the theoretical findings from the iFogSim simulations.1

### **1.3 Key Findings Summary**

The comprehensive evaluation conducted through both simulation and practical emulation yielded significant results that underscore the benefits of the proposed GVMP strategy.

* **Drastic Network Usage Reduction:** Simulation results demonstrated that GVMP achieves a dramatic reduction in total network usage, **up to 95% less than EWMP** in scaled-up scenarios. This is a direct result of its sibling-aware mechanism, which successfully contains processing within the local fog region, minimizing data transfers to the high-latency cloud.1  
* **Competitive Latency Performance:** While prioritizing network efficiency, GVMP maintains competitive, low application latency that is comparable to EWMP in many scenarios and vastly superior to the Cloud-Only approach.1  
* **Practical Validation of Performance Impact:** The virtual testbed results provided practical validation for the simulation findings. Experiments confirmed that module placement decisions have a direct and significant impact on performance. Shifting the final processing location from an edge gateway to the cloud increased the 95th percentile End-to-End (E2E) latency from approximately 482 ms to 5600 ms. Likewise, CPU load distribution shifted predictably across the tiers based on the placement configuration, confirming the resource implications of each strategy.1

Together, these findings demonstrate that GVMP's sibling-aware approach offers a more scalable, network-efficient, and resource-conscious solution for deploying latency-sensitive IoT applications compared to the strictly vertical logic of EWMP.1

## **2.0 Core Concepts: Module Placement in Fog Computing**

### **2.1 The Fog Computing Paradigm**

Fog computing extends the traditional cloud model by creating an intermediate layer of compute, storage, and networking services located between the centralized cloud datacenters and the data-generating IoT devices at the network edge.1 The primary motivation is to overcome the inherent limitations of the cloud, such as high latency and bandwidth consumption, which are unacceptable for a growing number of real-time IoT applications.1 By processing data closer to its source, Fog computing can significantly reduce application response time and alleviate congestion on the core network.1

However, this distributed and hierarchical environment introduces new complexities. Fog environments are typically composed of a wide range of heterogeneous devices with varying computational capabilities (CPU, RAM), storage, and network links.1 IoT applications are often decomposed into a series of interconnected processing modules, which can be represented as a Directed Acyclic Graph (DAG). The core challenge, and a central focus of this project, is the

**module placement problem**: determining the optimal assignment of these application modules to the available heterogeneous fog devices. This is a computationally complex problem, formally identified as NP-Hard, and an inefficient placement can easily negate the potential benefits of the Fog paradigm.1

### **2.2 Application Model: The EEG Tractor Beam Game**

To provide a concrete and representative use case for evaluating placement strategies, this project utilizes the **EEG Tractor Beam Game** application model.1 This scenario simulates a latency-sensitive, brain-computer interaction game where players' concentration levels, measured by EEG headsets, control an in-game action. The application's performance is directly tied to the low-latency feedback loop between the player's brain activity and the game's response.1

The application is decomposed into three primary software modules, forming a distinct data flow:

1. **Client Module (L1):** This module typically resides on the end-user's device (e.g., a smartphone). It receives raw EEG data from the sensor, performs initial validation and filtering, and sends the cleaned data upstream for further processing. It also receives processed game state information from upstream modules to update the user's display.1  
2. **Concentration Calculator Module (L2):** This computationally intensive module processes the filtered EEG data to compute the player's concentration level, often using signal processing techniques like Fast Fourier Transform (FFT). It sends the calculated concentration level back down to the client for immediate feedback and also sends player state updates upstream for global aggregation.1  
3. **Connector Module (L3):** This module is typically placed higher in the hierarchy (e.g., Gateway, Proxy, or Cloud). It aggregates game state information from multiple players, maintains the global game state, and distributes updates to all connected clients.1

The placement of the concentration\_calculator (L2) and connector (L3) modules is the central decision for any placement strategy, as their location dictates the path of data flow and therefore critically impacts the end-to-end latency of the user feedback loop and the total network traffic generated.1

### **2.3 Placement Strategies Under Evaluation**

#### **2.3.1 Cloud-Only Placement**

This represents the traditional, non-Fog approach. All core processing modules (concentration\_calculator and connector) are placed in the centralized cloud datacenter. Sensor data from the mobile device must traverse the entire network to the cloud for processing, and the resulting game state must travel all the way back. This strategy serves as a performance baseline, highlighting the high latency and network usage inherent in centralized processing for edge-generated data.1

#### **2.3.2 Edge-Ward Module Placement (EWMP)**

EWMP is a standard heuristic for Fog computing that embodies the core principle of processing data as close to the source as possible.1 The algorithm operates as follows:

* **Logic:** It considers devices along a strictly **vertical path** from the leaf node (e.g., the mobile device) upwards towards the cloud (Mobile \-\> Gateway \-\> Proxy \-\> Cloud).1  
* **Resource Check:** For a given application module, it first attempts to place it on the lowest-level device in the path. If that device has sufficient resources (e.g., CPU MIPS), the module is placed there.1  
* **Upward Shift:** If the current device is overloaded and cannot host the module, EWMP **immediately abandons placement at that level** and considers the direct parent device in the hierarchy. It does not explore other potential devices at the same hierarchical level (i.e., "siblings").1

While effective at reducing latency compared to the Cloud-Only model, EWMP's primary limitation is its strictly vertical search for resources. This can lead to inefficient resource utilization and unnecessary data traffic. For instance, if a mobile device's primary gateway is temporarily busy, EWMP will push the workload up to the higher-latency proxy or cloud, even if a neighboring gateway connected to the same proxy has ample free capacity.1

#### **2.3.3 Gateway Validation Module Placement (GVMP)**

GVMP is the novel strategy proposed and evaluated in this project to address the limitations of EWMP.1 It enhances the edge-ward approach by introducing a "sibling-aware" validation step before resorting to upward placement.

* **Logic:** GVMP follows the same bottom-up approach as EWMP but with a crucial addition. When a module cannot be placed on the target edge device due to resource constraints, it does not immediately shift the module upwards.1  
* **Sibling Validation:** Instead, it initiates a validation check, coordinated by the parent gateway. The gateway queries its other child nodes (the "siblings" of the original target device) to see if any of them have sufficient capacity to host the module.1  
* **Placement Hierarchy:** The placement decision follows a clear, three-step priority:  
  1. **Local Placement:** Attempt to place the module on the original target device.  
  2. **Sibling Placement:** If local placement fails, attempt to place the module on a capable sibling device within the same local fog region.  
  3. **Upward Placement:** Only if both local and sibling placements fail is the module shifted upwards to the parent device in the hierarchy.1

By prioritizing local and regional resources, GVMP aims to maximize resource utilization within the fog layer, thereby minimizing the need for costly data transfers to the higher-latency proxy and cloud tiers. This approach is designed to yield significant reductions in network traffic and improve overall system scalability and efficiency compared to EWMP.1

## **3.0 System Architecture of the Virtual Testbed**

To practically validate the performance implications of different module placement strategies, this project includes a comprehensive virtual testbed that emulates a multi-tier Fog computing environment. The architecture is designed to be configurable, observable, and reproducible.

### **3.1 Emulated Fog Hierarchy**

The testbed implements a four-tier hierarchical architecture that mirrors common IoT deployment models, extending from the network edge to a central cloud.1

* **Tier 1: Mobile Tier:** Consists of multiple Docker containers (mobile1\_1, mobile2\_1, etc.) that simulate end-user devices. Each mobile container runs a Python application that generates synthetic EEG data and initiates the processing pipeline.1  
* **Tier 2: Gateway Tier:** Comprises gateway containers (gateway1, gateway2) that act as the first point of aggregation for the mobile devices. They represent edge routers or local servers with moderate computational power.1  
* **Tier 3: Proxy Tier:** A single container (proxy\_py) represents a higher-level regional edge server or micro-datacenter. It aggregates traffic from multiple gateways and sits between the edge and the central cloud.1  
* **Tier 4: Cloud Tier:** A container (cloud\_py) represents the centralized cloud, offering the most significant computational resources but also incurring the highest network latency from the edge.1

This tiered topology is strictly enforced using dedicated Docker networks (gateway1\_mobiles\_net, proxy\_gateways\_net, cloud\_proxy\_net). This ensures that communication follows the intended hierarchical path (e.g., a mobile container can only communicate with its designated gateway, not directly with the proxy or cloud), accurately modeling real-world network segmentation.1

### **3.2 Technology Stack**

The virtual testbed is constructed using a suite of open-source technologies chosen for their robustness and suitability for creating a distributed systems laboratory.

* **Orchestration:** **Docker** and **Docker Compose** are used to define, build, and run the multi-container application. The entire architecture, including services, networks, resource limits, and dependencies, is declared in the docker-compose.yaml file.1  
* **Application Logic:** The services within each tier are implemented as **Python 3.12** applications using the **Flask** web framework. Flask provides lightweight HTTP endpoints for communication between tiers and for exposing performance metrics.1  
* **Network Emulation:** To simulate realistic network conditions between tiers, the testbed leverages the Linux **Traffic Control (tc)** utility with the **netem** (Network Emulator) queueing discipline. Entrypoint scripts (entrypoint.sh) within the mobile, gateway, and proxy containers read environment variables to apply configurable latency, jitter, and packet loss to their network interfaces, allowing for the study of system performance under various network quality scenarios.1  
* **Monitoring & Observability:** A comprehensive monitoring stack is deployed alongside the application to provide deep insights into system behavior:  
  * **Prometheus:** A time-series database that scrapes performance metrics exposed by the Flask applications via a /metrics endpoint.1  
  * **Grafana:** A visualization platform that queries Prometheus to display real-time dashboards of key performance indicators.1  
  * **Loki:** A log aggregation system designed for horizontally scalable, multi-tenant log storage.1  
  * **Promtail:** An agent that collects logs from the Docker containers and ships them to Loki.1

### **3.3 Application Logic and Shared Modules**

To promote code reusability and maintain a clean separation of concerns, the core logic of the EEG application is encapsulated in a set of shared Python classes.

* **Shared Modules:** The shared\_modules/ directory contains the implementations for the ClientModule, ConcentrationCalculatorModule, and ConnectorModule, which correspond to the L1, L2, and L3 processing steps, respectively. It also includes helper modules for metrics definition and cpu\_monitor functionality.1  
* **Dynamic Loading:** Each tier's main application script (mobile.py, gateway.py, etc.) dynamically loads and initializes these shared modules at startup based on its configured \*\_PROCESSING\_LEVEL environment variable. This allows the behavior of each tier to be controlled externally without changing the code.1  
* **Data Generation:** The mobile.py application includes a SensorSimulator class that generates a continuous stream of synthetic EEG data, which serves as the input for the entire system and kicks off the data processing pipeline.1

A key design feature of this architecture is the intrinsic link between the simulation of resource constraints and the monitoring of their effects. The docker-compose.yaml file explicitly defines heterogeneous resource limits for each tier (e.g., a mobile container is limited to 0.05 CPUs, while the cloud has 1 CPU), directly modeling the core Fog computing challenge of resource heterogeneity.1 The

cpu\_monitor.py module is specifically designed to read these cgroup-enforced limits from the container's filesystem. It then calculates a **normalized CPU utilization percentage**, which represents the current load relative to the container's maximum allocated capacity. This normalized metric, rather than an absolute CPU value, is the primary CPU indicator visualized in the Grafana dashboard. This provides a direct and accurate measure of resource pressure on each device, making it possible to clearly observe how different module placement configurations stress the constrained resources of the Fog hierarchy.1

## **4.0 Getting Started**

This section provides the necessary steps to clone the repository and prepare the environment for running the simulation.

### **4.1 Prerequisites**

Before you begin, ensure you have the following software installed on your system:

* Docker Engine  
* Docker Compose (typically included with Docker Desktop)  
* A Git client for cloning the repository

### **4.2 Installation**

1. Clone the repository:  
   Open a terminal and clone the project repository to your local machine.  
   Bash  
   git clone https://github.com/RudraGarg/CS300.git

2. Navigate to the project directory:  
   Change into the newly created project directory.  
   Bash  
   cd CS300

### **4.3 Initial Setup**

All configuration for the virtual testbed is managed through the .env file located in the root of the project directory. The repository includes a pre-configured .env file with default values for a multi-tier placement scenario.1 You can modify this file directly to change experiment parameters before launching the environment. No other setup steps are required.

## **5.0 Configuration**

The entire behavior of the virtual testbed, including module placement and network conditions, is controlled via environment variables defined in the .env file. This section details the key configuration options.

### **5.1 Module Placement Configuration**

The placement of application modules is controlled by the \*\_PROCESSING\_LEVEL variables. These variables determine the highest level of processing (L1, L2, or L3) that a service in a given tier is permitted to execute. The application logic within each service reads its level at startup and uses it to decide whether to process incoming data locally or forward it to the next tier up.1

The processing levels are defined as:

* 0: **Passthrough:** The service will not perform any application logic and will forward all requests upstream. (Applicable to Gateway and Proxy).  
* 1: **Client (L1):** The service can execute the Client module.  
* 2: **Calculator (L2):** The service can execute up to the Concentration Calculator module.  
* 3: **Connector (L3):** The service can execute the entire application pipeline up to the final Connector module.

The following table details the placement configuration variables:

| Variable | Description | Default Value | Example Effect |
| :---- | :---- | :---- | :---- |
| MOBILE\_PROCESSING\_LEVEL | Sets the maximum processing level for the Mobile tier containers. It is typically set to 1 or higher, as the Client module (L1) must run to process raw sensor data. | 1 | Setting to 2 would cause the Concentration Calculator to run directly on the mobile device. |
| GATEWAY\_PROCESSING\_LEVEL | Sets the maximum processing level for the Gateway tier containers. | 2 | With the default value, the gateway will execute the Concentration Calculator (L2) but will forward the result to the Proxy for L3 processing. |
| PROXY\_PROCESSING\_LEVEL | Sets the maximum processing level for the Proxy tier container. | 3 | With the default value, the proxy is configured to perform the final Connector (L3) processing step. |
| CLOUD\_PROCESSING\_LEVEL | Sets the maximum processing level for the Cloud tier container. It is the final tier, so it typically has the capability to run all modules. | 3 | This level is relevant in scenarios where processing is offloaded from the Proxy to the Cloud. |

### **5.2 Network Emulation Configuration**

The testbed can simulate realistic network conditions between the tiers. This feature is controlled by the following variables in the .env file, which are used by entrypoint.sh scripts within the containers to configure Linux Traffic Control (tc).1

| Variable | Description | Default Value | Unit |
| :---- | :---- | :---- | :---- |
| ENABLE\_LATENCY | Master switch to enable or disable all network emulation. Set to true to activate latency, jitter, and loss. | true | Boolean |
| LATENCY\_MOBILE\_TO\_GATEWAY | The one-way network latency added to packets sent from a Mobile container to its Gateway. | 50ms | ms |
| LATENCY\_GATEWAY\_TO\_PROXY | The one-way network latency added to packets sent from a Gateway container to the Proxy. | 100ms | ms |
| LATENCY\_PROXY\_TO\_CLOUD | The one-way network latency added to packets sent from the Proxy container to the Cloud. | 300ms | ms |
| JITTER\_MOBILE\_TO\_GATEWAY | Random variation applied to the LATENCY\_MOBILE\_TO\_GATEWAY value. | 5ms | ms |
| JITTER\_GATEWAY\_TO\_PROXY | Random variation applied to the LATENCY\_GATEWAY\_TO\_PROXY value. | 10ms | ms |
| JITTER\_PROXY\_TO\_CLOUD | Random variation applied to the LATENCY\_PROXY\_TO\_CLOUD value. | 30ms | ms |
| LOSS\_MOBILE\_TO\_GATEWAY | Percentage of packets to be randomly dropped on the link from Mobile to Gateway. (Commented out by default). | N/A | % |

## **6.0 Running the Simulation**

Follow these steps to launch, verify, and shut down the virtual testbed environment.

### **6.1 Launching the Environment**

From the root directory of the project, execute the following command to build the container images and start all services in detached mode:

Bash

docker-compose up \--build \-d

* \--build: This flag forces Docker Compose to rebuild the images from the Dockerfiles. It is recommended for the first run or any time you make changes to the application code or Dockerfiles.  
* \-d: This flag runs the containers in the background (detached mode).

The initial startup process may take several minutes as Docker downloads the base images and builds the application containers.

### **6.2 Verifying the Setup**

After launching the services, you can check their status using the following command:

Bash

docker-compose ps

You should see a list of all services defined in docker-compose.yaml (e.g., grafana, prometheus, gateway1, mobile1\_1, etc.). Allow a few minutes for the services to initialize. The STATUS column should eventually show running (healthy) for services with a health check configured. The health checks ensure that services start in the correct order (e.g., mobile clients will wait for their gateway to be healthy before starting).1

### **6.3 Accessing Services**

The key services of the testbed are exposed on your local machine's ports. You can access their web UIs using the following URLs:

| Service | Host Port | URL | Purpose |
| :---- | :---- | :---- | :---- |
| **Grafana** | 3000 | http://localhost:3000 | Main dashboard for visualizing all performance metrics. |
| **Prometheus** | 9095 | http://localhost:9095 | Prometheus UI for ad-hoc metric queries and target status. |
| **Loki** | 3100 | http://localhost:3100 | Loki service endpoint (typically accessed via Grafana). |
| Cloud App | 8081 | http://localhost:8081/health | Health check endpoint for the Cloud service. |
| Proxy App | 8080 | http://localhost:8080/health | Health check endpoint for the Proxy service. |
| Gateway 1 | 9091 | http://localhost:9091/health | Health check endpoint for the Gateway 1 service. |
| Gateway 2 | 9092 | http://localhost:9092/health | Health check endpoint for the Gateway 2 service. |
| Mobile 1-1 Metrics | 9093 | http://localhost:9093/metrics | Prometheus metrics endpoint for the mobile1\_1 service. |

### **6.4 Stopping the Environment**

To stop and remove all running containers, networks, and volumes created by the simulation, run the following command from the project's root directory:

Bash

docker-compose down

If you also wish to remove the named volumes that store Prometheus and Grafana data, add the \-v flag:

Bash

docker-compose down \-v

## **7.0 Monitoring and Interpreting Results**

The primary interface for monitoring the experiment and interpreting its results is the Grafana dashboard. It provides a real-time, visual representation of the system's performance under the configured placement and network conditions.

### **7.1 Accessing the Dashboard**

1. Navigate to http://localhost:3000 in your web browser.  
2. The main dashboard, titled **"EEG Fog Sim"**, should load automatically. This is configured as the default home dashboard.1 All dashboards are provisioned automatically from the  
   config/grafana-dashboards/ directory.1

The dashboard is not just a static display but a dynamic narrative of the system's behavior. The panels are designed to be read together to understand the causal chain of events stemming from a configuration change. By modifying the .env file and restarting the environment, you can observe how a change in placement strategy (the cause) directly impacts data flow, resource consumption, and ultimately, application performance (the effects). This transforms the user from a passive observer into an active experimenter, allowing for a deep understanding of the trade-offs involved in Fog computing module placement.

### **7.2 Key Performance Indicators (KPIs) \- A Guided Tour**

The dashboard is organized into rows, each focusing on a different aspect of the system. The following are the most critical panels for evaluating module placement strategies.1

#### **7.2.1 End-to-End (E2E) Latency (Panel ID: 104\)**

* **What it shows:** This panel displays the total wall-clock time from the moment a data packet is created in a mobile container until it completes the final (L3 \- Connector) processing step. This is the most critical metric for user-perceived application responsiveness.1  
* **How to read it:** The panel shows two key values: the **average** latency and the **95th percentile (p95)** latency. The p95 value is particularly important as it represents a worst-case experience for the majority of users. Crucially, the metric is labeled with final\_tier (e.g., p95 (gateway) or avg (cloud)), which tells you *where* in the hierarchy the final processing occurred.1  
* **Why it matters:** This panel provides direct, quantitative evidence of the performance impact of module placement. As observed in the project's experiments, moving the final processing tier from the gateway to the cloud results in a dramatic increase in E2E latency.1 This panel allows you to replicate and visualize that finding instantly.

#### **7.2.2 Final Processing Location (Panel ID: 400\)**

* **What it shows:** This pie chart provides an at-a-glance summary of where the final connector (L3) module is being executed across the entire system.1  
* **How to read it:** Each slice of the pie represents a tier (mobile, gateway, proxy, or cloud). The size of the slice corresponds to the percentage of total L3 module executions occurring on that tier over the last five minutes.1  
* **Why it matters:** This panel gives an immediate visual confirmation of the placement strategy you have configured in the .env file. If you configure an edge-heavy scenario, the "gateway" slice should dominate. If you configure a cloud-only scenario, the "cloud" slice will be 100%. It directly visualizes the outcome of your \*\_PROCESSING\_LEVEL settings.

#### **7.2.3 CPU Utilization (Normalized) (Panel IDs: 301, 302, 303, 311\)**

* **What it shows:** These time-series graphs display the CPU load for each container in the Mobile, Gateway, Proxy, and Cloud tiers, respectively.1  
* **How to read it:** The y-axis represents the CPU load as a percentage from 0-100%. This is a **normalized** value, meaning it shows the usage relative to the CPU limit defined for that container in docker-compose.yaml. A value of 95% on a gateway means it is using 95% of its *allocated* resources (e.g., 95% of 0.1 cores) and is approaching its capacity limit.1  
* **Why it matters:** This directly visualizes the resource consumption impact of placement decisions, corresponding to the "CPU Utilization Analysis" in the research report.1 It clearly shows how the computational load shifts across the Fog hierarchy depending on the placement configuration. This is the key metric for identifying potential resource bottlenecks and evaluating how well a strategy distributes load.

#### **7.2.4 Module Execution & Passthrough Rate (per Tier) (Panel IDs: 401, 411, 421\)**

* **What it shows:** For the Mobile, Gateway, and Proxy tiers, this panel displays two key time-series metrics: the rate at which application modules are being executed locally, and the rate at which requests are being passed through to the next higher tier without local processing.1  
* **How to read it:** In a scenario where a gateway is configured for passthrough (GATEWAY\_PROCESSING\_LEVEL=0), its "Passthrough Rate" will be high, and its "Module Execution Rate" will be zero. Conversely, if it is configured to process up to L2, its calculator execution rate will be high, and its passthrough rate will be zero.  
* **Why it matters:** This panel provides a detailed, real-time view of the data flow and workload distribution throughout the system. It allows you to see precisely how each tier is handling incoming requests based on the configured placement strategy, confirming that the system is behaving as intended.

## **8.0 Experiment Scenarios**

To demonstrate the capabilities of the testbed and replicate the core findings of the research, you can configure the .env file for the following scenarios. After changing the .env file, you must restart the environment with docker-compose down && docker-compose up \--build \-d.

### **8.1 Scenario 1: Emulating Cloud-Only Placement**

This scenario forces all core processing (L2 and L3) to occur in the central cloud, simulating the traditional model without Fog computing.

**Configuration (.env):**

Code snippet

\# Module Placement Levels  
MOBILE\_PROCESSING\_LEVEL=1  
GATEWAY\_PROCESSING\_LEVEL=0  
PROXY\_PROCESSING\_LEVEL=0  
CLOUD\_PROCESSING\_LEVEL=3

**Expected Outcome on Grafana Dashboard:**

* **Final Processing Location:** The pie chart will show 100% for the cloud slice.  
* **E2E Latency:** Will be very high (e.g., \>1500ms), and the stat panel will be labeled with final\_tier=cloud.  
* **CPU Utilization:** The Cloud CPU panel will show the highest relative load, while Gateway and Proxy CPU usage will be minimal (handling only network forwarding).  
* **Passthrough Rate:** The Gateway and Proxy tiers will show a high "Passthrough Rate," as they are not executing any application modules.

### **8.2 Scenario 2: Emulating Edge-Heavy Placement (GVMP/EWMP Best Case)**

This scenario places all processing as close to the edge as possible, with the Gateway performing all steps from L1 to L3. This emulates a best-case scenario for an edge-focused strategy where the edge device has sufficient resources.

**Configuration (.env):**

Code snippet

\# Module Placement Levels  
MOBILE\_PROCESSING\_LEVEL=1  
GATEWAY\_PROCESSING\_LEVEL=3  
PROXY\_PROCESSING\_LEVEL=3  
CLOUD\_PROCESSING\_LEVEL=3

**Expected Outcome on Grafana Dashboard:**

* **Final Processing Location:** The pie chart will show 100% for the gateway slice. The proxy and cloud slices will be zero.  
* **E2E Latency:** Will be significantly lower than the Cloud-Only scenario (e.g., \~200-500ms), and the stat panel will be labeled with final\_tier=gateway.  
* **CPU Utilization:** The Gateway CPU panels will show a significantly higher load, as they are now responsible for both L2 (calculator) and L3 (connector) processing.  
* **Passthrough Rate:** The Gateway tier will show a zero "Passthrough Rate". The Proxy tier will show no activity as no data is forwarded to it.

### **8.3 Scenario 3: Emulating a Multi-Tier Placement (Default)**

This scenario distributes the workload across multiple tiers, with the Client (L1) on Mobile, the Calculator (L2) on the Gateway, and the Connector (L3) on the Proxy. This is the default configuration in the repository.

**Configuration (.env):**

Code snippet

\# Module Placement Levels  
MOBILE\_PROCESSING\_LEVEL=1  
GATEWAY\_PROCESSING\_LEVEL=2  
PROXY\_PROCESSING\_LEVEL=3  
CLOUD\_PROCESSING\_LEVEL=3

**Expected Outcome on Grafana Dashboard:**

* **Final Processing Location:** The pie chart will show 100% for the proxy slice.  
* **E2E Latency:** Will be at an intermediate level, higher than the Edge-Heavy scenario but lower than the Cloud-Only one (e.g., \~800-3600ms), labeled with final\_tier=proxy.  
* **CPU Utilization:** Load will be distributed. The Mobile tier will have a baseline load, the Gateway tier will show moderate load from L2 processing, and the Proxy tier will show moderate load from L3 processing. The Cloud tier will be idle.  
* **Passthrough Rate:** The Gateway will show zero passthrough (as it processes to L2), and the Proxy will show zero passthrough (as it performs the final L3 step).

## **9.0 Codebase Deep Dive**

This section provides a brief overview of the key source code files in the repository.

### **9.1 Service Application Logic**

* mobile/mobile.py: Simulates the IoT device. Its main loop generates synthetic sensor data, performs local processing up to its configured MOBILE\_PROCESSING\_LEVEL, and uses a GatewayConnector class to send data upstream. It is the starting point of the data flow.1  
* gateway/gateway.py: Represents the first tier of Fog nodes. It exposes a Flask endpoint that receives data from mobile clients. Based on its GATEWAY\_PROCESSING\_LEVEL, it either processes the data further or acts as a passthrough, forwarding the request to the proxy.1  
* proxy\_py/proxy\_app.py: Represents a higher-level Fog/Edge server. It receives data from the gateways and, based on its PROXY\_PROCESSING\_LEVEL, either performs the final processing steps or forwards the request to the cloud.1  
* cloud\_py/cloud\_app.py: Represents the centralized cloud. It is the final destination in the hierarchy and performs any processing that has been offloaded from the lower tiers.1

### **9.2 Shared Modules (shared\_modules/)**

This directory contains reusable Python modules that are shared across all service tiers, ensuring consistent application logic.1

* client\_module.py: Implements the L1 application logic, including data validation, quality checking, and filtering of raw EEG data.1  
* concentration\_calculator\_module.py: Implements the L2 logic. It uses NumPy to perform a Fast Fourier Transform (FFT) on the EEG signal to calculate the power in the alpha band, which is used as a proxy for user concentration.1  
* connector\_module.py: Implements the final L3 logic, which involves packaging the data for final consumption (e.g., updating a global game state).1  
* metrics.py: Provides a centralized definition for all Prometheus metrics used in the project (e.g., MODULE\_EXECUTIONS, E2E\_LATENCY, CPU\_UTILIZATION). This ensures consistent metric naming and labeling across all services.1  
* cpu\_monitor.py: A crucial utility module that provides functions to read CPU usage information directly from the container's cgroup filesystem. Its get\_container\_cpu\_percent\_non\_blocking() function calculates CPU usage both as a raw percentage and as a percentage normalized against the container's allocated CPU quota, which is essential for accurately assessing resource pressure on heterogeneous devices.1

## **10.0 Citation and Acknowledgements**

This repository and the experiments it enables are based on the research conducted for the B.Tech. project report cited below. When using this work, please provide appropriate attribution.

### **Primary Work**

Garg, Rudra. (2025). *Comparative Performance Evaluation of GVMP and Edge-Ward Module Placement in Fog Computing*. B.Tech. Project (CS 300\) Report, Indian Institute of Information Technology Guwahati. 1

### **Key Referenced Work**

The GVMP strategy evaluated in this project was first proposed in the following paper:

Panda, S. K., Tyagi, D., & Rout, R. R. (2024). GVMP: A novel internet of things application module placement strategy for heterogeneous infrastructure using iFogSim. In *2024 15th International Conference on Computing Communication and Networking Technologies (ICCCNT)*. IEEE. 1

### **Acknowledgements**

This work utilizes concepts and models from the **iFogSim** toolkit for the simulation-based portion of the evaluation.1