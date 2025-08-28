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

### 3. Set the KRUIZE_URL environment variable

NOTE: If env variable is not set, KRUIZE_URL will default to http://localhost:8080, refer [application.properties](src/main/resources/application.properties)

```
export KRUIZE_URL=http://kruize-openshift-tuning.apps.<cluster_name>.lab.upshift.rdu2.redhat.com
```


### 4. Testing with the MCP Inspector Tool 🔬

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
  - `listCostOptimizedRecommendations` - Retrieves available cost recommendations for the specified experiment name.
  - `listAllExperiments` - Retrieves a list of all available experiments.

![InspectorTool.png](InspectorTool.png)