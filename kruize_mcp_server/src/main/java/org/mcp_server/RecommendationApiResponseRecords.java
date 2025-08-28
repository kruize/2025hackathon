package org.mcp_server;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Container for API response records for list recommendations.
 */
public final class RecommendationApiResponseRecords {
    private RecommendationApiResponseRecords() {}

    // --- Final, clean output format ---
    public record FinalCostResult(
            String namespace,
            Optional<String> containerName,
            List<Notification> notifications,
            ResourceGroup currentUsage,
            List<CostRecommendation> costRecommendations
    ) {}


    public record TimestampData(
            ResourceGroup current,
            @JsonProperty("recommendation_terms") Map<String, RecommendationTerm> recommendationTerms
    ) {}

    public record CostRecommendation(
            String term,
            int durationInHours,
            Optional<ResourceGroup> config,
            Optional<ResourceGroup> variation
    ) {}

    // --- Records for navigating the JSON structure ---
    public record ResourceMetric(double amount, String format) {}
    public record ResourceConfig(ResourceMetric cpu, ResourceMetric memory) {}
    public record ResourceGroup(ResourceConfig requests, ResourceConfig limits) {}

    public record RecommendationEngine(
            ResourceGroup config,
            ResourceGroup variation
    ) {}

    public record RecommendationTerm(
            @JsonProperty("duration_in_hours") int durationInHours,
            @JsonProperty("recommendation_engines") Map<String, RecommendationEngine> recommendationEngines
    ) {}

    public record Notification(String type, String message, int code) {}

    public record RecommendationData(
            String version,
            Map<String, Notification> notifications,
            Map<String, TimestampData> data
    ) {}

    // Namespace record
    public record Namespace(
            @JsonProperty("namespace") String namespace,
            Optional<RecommendationData> recommendations
    ) {}

    // Container record to include recommendations
    public record Container(
            @JsonProperty("container_name") String containerName,
            @JsonProperty("container_image_name") String containerImageName,
            Optional<RecommendationData> recommendations
    ) {}

    public record KubernetesObject(
            String namespace,
            String type,
            String name,
            Optional<List<Container>> containers,
            Optional<Namespace> namespaces
    ) {}

    // Top-level object in the JSON array
    public record Recommendations(
            @JsonProperty("experiment_name") String experimentName,
            @JsonProperty("experiment_type") String experimentType,
            @JsonProperty("kubernetes_objects") List<KubernetesObject> kubernetesObjects
    ) {}
}