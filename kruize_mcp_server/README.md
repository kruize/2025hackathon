## 🚀 Getting Started

Follow these steps to build the project and prepare it for running.

### 1. Clone the Repository

First, clone this repository to your local machine.
```
git clone git@github.com:kruize/2025hackathon.git
cd kruize_mcp_server
```


### 2. Build the Project
Use the Maven Wrapper (mvnw) to compile the source code and package it into an executable JAR file.
```
./mvnw install
```

This command will run tests and create a .jar file in the target/ directory.

### 4. Deploy kruize using either [local monitoring](https://github.com/kruize/kruize-demos/tree/main/monitoring/local_monitoring) or [bulk](https://github.com/kruize/kruize-demos/tree/main/monitoring/local_monitoring/bulk_demo) kruize-demos scripts

#### 1. Local monitoring demo creates two container experiments and generates recommendations for TFB benchmark workloads
```
./local_monitoring_demo.sh -c openshift -e container
```
 OR

#### 2. Bulk demo creates experiments and generates recommendations for all the containers present in the cluster
```
./bulk_service_demo.sh -c openshift
```

### 4. Set the KRUIZE_URL environment variable

NOTE: If env variable is not set, KRUIZE_URL will default to http://localhost:8080, refer [application.properties](src/main/resources/application.properties)

```
export KRUIZE_URL=http://kruize-openshift-tuning.apps.<cluster_name>.lab.upshift.rdu2.redhat.com
```


### 5. Testing with the MCP Inspector Tool 🔬

##### 1. Install the Inspector Tool

You only need to run this command once to install the tool globally on your machine.

```
npm install -g @modelcontextprotocol/inspector@0.11.0
```

##### 2. Run the Inspector Tool

Once the build for Kruize MCP server is ready (e.g., with ./mvnw install), open a new terminal window and run the following command to launch the inspector and connect to your server.

```
npx @modelcontextprotocol/inspector
```
The Inspector will now be connected to your server, allowing you to call your tools.

- NOTE: When testing the Kruize MCP server tools with the Bulk demos recommendations API, increase the timeout in the MCP Inspector tool to prevent timeout errors.
- Navigate to Configuration increase `Request Timeout` to `60000(60s)` and `Maximum Total Timeout` to `180000(3mins)`


##### 3. Connect to MCP server using Inspector tool

- Select the `Transport Type` as `STDIO`
- Pass `java` as `Command`
- In the `Arguments` field, provide the full path to the JAR file located in the target directory.
  - for example 
  ```
  -jar /home/username/2025hackathon/kruize_mcp_server/target/kruize_mcp_server-1.0-SNAPSHOT-runner.jar`
  ```
- Click on `Connect` button
- Once successfully connected try to list the tools
- Current list of tools supported:
  - `listAllRecommendations` - Retrieves a list of all available recommendations.
  - `getCostOptimizedRecommendations` - Retrieves available cost recommendations for all the experiments.
  - `listAllExperiments` - Retrieves a list of all available experiments.
  - `getIdleWorkloads` - Retrieves idle workloads which have specific notification code `323001`. Optionally includes cost recommendations data.

![InspectorTool.png](InspectorTool.png)
