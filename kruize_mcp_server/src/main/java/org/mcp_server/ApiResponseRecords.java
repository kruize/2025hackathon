package org.mcp_server;

import java.util.List;

public class ApiResponseRecords {
    private ApiResponseRecords() {}


    public record Experiment(String experiment_id, String experiment_name, String status, String target_cluster, String mode, String experiment_type) {
    }

    public record Recommendations(String experiment_name, String experiment_type, List<KubernetesObjects> kubernetes_objects) {
    }

    public record KubernetesObjects(String namespace, String type, String name, List<Container_k8s_object> containers) {
    }

    public record Container_k8s_object(String container_name, String container_image_name) {
    }

    public record Namespace_k8s_object(String namespace) {
    }

}
