import os
import json
import requests

DATAGEN_URL = "http://127.0.0.1:8000"

CREATE_DATA_ENDPOINT = "/data/create"
GET_DATA_ENDPOINT = "/data/get"
COST_DATA_ENDPOINT = "/data/cost"
CLUSTER_DATA_ENDPOINT = "/data/cluster"
RAW_DATA_ENDPOINT = GET_DATA_ENDPOINT + "/raw"
AGGREGATE_DATA_ENDPOINT = GET_DATA_ENDPOINT + "/agg"
RECOMMENDATION_DATA_ENDPOINT = GET_DATA_ENDPOINT + "/recommendations"

CREATE_DATA_URL = f"{DATAGEN_URL}{CREATE_DATA_ENDPOINT}"
GET_DATA_URL = f"{DATAGEN_URL}{GET_DATA_ENDPOINT}"
CLUSTER_DATA_URL = f"{DATAGEN_URL}{CLUSTER_DATA_ENDPOINT}"
COST_DATA_URL = f"{DATAGEN_URL}{COST_DATA_ENDPOINT}"
RAW_DATA_URL = f"{DATAGEN_URL}{RAW_DATA_ENDPOINT}"
AGGREGATE_DATA_URL = f"{DATAGEN_URL}{AGGREGATE_DATA_ENDPOINT}"
RECOMMENDATION_DATA_URL = f"{DATAGEN_URL}{RECOMMENDATION_DATA_ENDPOINT}"

LAST = "15d"
AGG_FUNC = "max"
FOREACH = "15m"

with open("workloads.json", "r") as f:
    workloads = json.load(f)

for workload in workloads:
    namespace = workload["namespace"]
    workload_name = workload["workload_name"]

    dir_path = os.path.join("generated", namespace, workload_name)
    os.makedirs(dir_path, exist_ok=True)

    input_file = os.path.join(dir_path, "input.json")
    with open(input_file, "w") as f:
        json.dump(workload, f, indent=2)

    try:
        create_resp = requests.post(CREATE_DATA_URL, json=workload)
        create_resp.raise_for_status()
        print(f"[SUCCESS] Created data for {namespace}/{workload_name}")
    except requests.RequestException as e:
        print(f"[ERROR] Failed to create data for {namespace}/{workload_name}: {e}")
        print(f"[ERROR] {create_resp.json()}]")
        # if create_resp.status_code != 409:
        #     continue
        continue

    raw_params = {
        "namespace": namespace,
        "workload_type": workload["workload_type"],
        "workload_name": workload["workload_name"],
        "container_name": workload["container_name"],
        "last": LAST,
        "agg_func": AGG_FUNC,
        "foreach": FOREACH,
    }

    try:
        raw_resp = requests.get(RAW_DATA_URL, params=raw_params)
        raw_resp.raise_for_status()
        raw_file = os.path.join(dir_path, "raw.json")
        with open(raw_file, "w") as f:
            json.dump(raw_resp.json(), f, indent=2)
        print(f"[SUCCESS] Saved raw.json for {namespace}/{workload_name}")
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch raw data for {namespace}/{workload_name}: {e}")
        print(f"[ERROR] {raw_resp.json()}]")

    rec_params = {
        "namespace": namespace,
        "workload_type": workload["workload_type"],
        "workload_name": workload["workload_name"],
        "container_name": workload["container_name"],
    }

    try:
        rec_resp = requests.get(RECOMMENDATION_DATA_URL, params=rec_params)
        rec_resp.raise_for_status()
        rec_file = os.path.join(dir_path, "rec.json")
        with open(rec_file, "w") as f:
            json.dump(rec_resp.json(), f, indent=2)
        print(f"[SUCCESS] Saved rec.json for {namespace}/{workload_name}")
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch recommendations for {namespace}/{workload_name}: {e}")

generated_path = os.path.join("generated")

cost_resp = requests.get(COST_DATA_URL)
cost_resp.raise_for_status()
cost_file = os.path.join(generated_path, "costs.json")
with open(cost_file, "w") as f:
    json.dump(cost_resp.json(), f, indent=2)
    print(f"[SUCCESS] Saved costs.json")

cluster_resp = requests.get(CLUSTER_DATA_URL)
cluster_resp.raise_for_status()
cluster_file = os.path.join(generated_path, "cluster.json")
with open(cluster_file, "w") as f:
    json.dump(cluster_resp.json(), f, indent=2)
    print(f"[SUCCESS] Saved cluster.json")


