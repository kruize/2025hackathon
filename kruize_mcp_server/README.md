# Kruize MCP Server

MCP Server providing tools for Kruize recommendations and experiments.

## Quick Start

Choose your platform:
- **[OpenShift](#openshift)** - Deploy on OpenShift clusters
- **[Minikube](#minikube)** - Deploy on Minikube for local development

---

## OpenShift

### Deploy

```bash
# 1. Clone and build
git clone git@github.com:kruize/2025hackathon.git
cd kruize_mcp_server
./mvnw install

# 2. Deploy Kruize
./local_monitoring_demo.sh -c openshift -e container

# 3. Build and push image
docker build -t <registry>/<username>/kruize-mcp-server:latest .
docker push <registry>/<username>/kruize-mcp-server:<tag>

# 4. Deploy MCP server (in openshift-tuning namespace)
oc apply -f manifests/kruize_mcp_server.yaml -n openshift-tuning
oc expose service kruize-mcp-server-service -n openshift-tuning

# 5. Get URL and connect Inspector
oc get route kruize-mcp-server-service -n openshift-tuning --template='{{ .spec.host }}'
npx @modelcontextprotocol/inspector http://<route-url>/mcp/
```

**Deployment Location:** `openshift-tuning` namespace (same as Kruize)

---

## Minikube

### Deploy

```bash
# 1. Clone
git clone git@github.com:kruize/2025hackathon.git
cd kruize_mcp_server

# 2. Deploy Kruize (sets up Minikube + Prometheus)
git clone https://github.com/kruize/kruize-demos.git
cd kruize-demos/monitoring/local_monitoring
./local_monitoring_demo.sh -c minikube -f -e container

# 3. Deploy MCP server
cd kruize_mcp_server
kubectl apply -f manifests/kruize_mcp_server_minikube.yaml
kubectl wait --for=condition=ready pod -l app=kruize-mcp-server -n monitoring --timeout=120s

# 4. Port forward and connect Inspector
kubectl port-forward -n monitoring service/kruize-mcp-server-service 8082:8082
npx @modelcontextprotocol/inspector http://localhost:8082/mcp/
```

**Note:** Kruize MCP server uses port 8082 (Kruize uses 8080/8081)

---

## MCP Tools

- `listAllRecommendations` - Get all recommendations
- `getCostOptimizedRecommendations` - Get cost recommendations for all the experiments
- `listAllExperiments` - Get all experiments
- `getIdleWorkloads` - Get idle workloads which have specific notification code 323001. Optionally includes cost recommendations data

---

## Configuration

**Inspector Timeouts:** Set Request Timeout = `60000`, Max Total Timeout = `180000`

**Environment Variables:**
- `KRUIZE_URL` - Kruize service URL (default: `http://localhost:8080`)
- `QUARKUS_HTTP_PORT` - MCP server port (8080 for OpenShift, 8082 for Minikube)

---

## Local Development

### Run from JAR

```bash
# 1. Build the project
./mvnw clean install

# 2. Run the JAR file (defaults to port 8080)
java -jar target/kruize_mcp_server-1.0-SNAPSHOT-runner.jar

# 3. Connect Inspector
npx @modelcontextprotocol/inspector http://localhost:8080/mcp/
```

**Custom Configuration:**
```bash
# Use port 8082 (if Kruize is running locally on 8080/8081)
QUARKUS_HTTP_PORT=8082 java -jar target/kruize_mcp_server-1.0-SNAPSHOT-runner.jar

# Connect to remote Kruize instance
KRUIZE_URL=http://your-kruize-url:8080 java -jar target/kruize_mcp_server-1.0-SNAPSHOT-runner.jar
```
---
