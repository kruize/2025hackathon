package org.mcp_server;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkiverse.mcp.server.Tool;
import org.eclipse.microprofile.rest.client.inject.RestClient;
import jakarta.inject.Inject;
import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.mcp_server.ExperimentApiResponseRecords.Experiment;
import org.mcp_server.RecommendationApiResponseRecords.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class KruizeTools {
    private static final Logger log = LoggerFactory.getLogger(KruizeTools.class);

    @Inject
    @RestClient
    KruizeApiClient apiClient; // Inject the client you defined

    @Inject
    ObjectMapper objectMapper;

    @Tool(description = "Retrieves a list of all available experiments.")
    public String listAllExperiments() {
        try {
            List<Experiment> experiments = apiClient.getAllExperiments();

            if (experiments == null || experiments.isEmpty()) {
                // Return a valid empty JSON array
                return "[]";
            }

            return objectMapper.writeValueAsString(experiments);

        } catch (JsonProcessingException e) {
            return "{\"error\": \"Failed to serialize experiment data to JSON.\"}";
        } catch (Exception e) {
            return "{\"error\": \"Failed to retrieve experiments from the API.\"}";
        }
    }

    @Tool(description = "Retrieves a list of all available recommendations.")
    public String listAllRecommendations() {
        try {
            List<Recommendations> apiResponse = apiClient.getAllRecommendations(); // Pass null for no name filter

            if (apiResponse == null) {
                return "[]";
            }

            String jsonOutput = objectMapper.writeValueAsString(apiResponse);
            return jsonOutput;

        } catch (Exception e) {
            return "{\"error\": \"Failed to retrieve recommendations from the API: " + e.getMessage() + "\"}";
        }
    }


    private record RecommendationSource(String parentNamespace, Optional<String> sourceName, Optional<RecommendationData> recommendations) {}

    @Tool(description = "Retrieves available cost optimized recommendations.")
    public String getCostOptimizedRecommendations() {
        try {
            List<Recommendations> apiResponse = apiClient.getAllRecommendations();
            List<FinalCostResult> allFinalResults = new ArrayList<>();

            // 1. Loop through each Recommendation object in the API response list
            for (Recommendations recommendations : apiResponse) {

                String experimentName = recommendations.experimentName();
                String experimentType = recommendations.experimentType();

                // 2. Process the kubernetes_objects for the current experiment
                List<KubernetesObject> kubernetesObjects = Optional.ofNullable(recommendations.kubernetesObjects())
                        .orElse(Collections.emptyList());

                for (KubernetesObject k8sObject : kubernetesObjects) {

                    // 3. Create the unified stream of containers and namespaces
                    Stream<RecommendationSource> sourceStream = Stream.concat(
                            k8sObject.containers().orElse(Collections.emptyList()).stream()
                                    .map(c -> new RecommendationSource(k8sObject.namespace(), Optional.of(c.containerName()), c.recommendations())),
                            k8sObject.namespaces().stream()
                                    .map(n -> new RecommendationSource(n.namespace(), Optional.empty(), n.recommendations()))
                    );

                    // 4. Map the sources to the final result, now with easy access to parent fields
                    sourceStream
                            .map(source -> {
                                if (source.recommendations().isEmpty()) return null;

                                List<Notification> notifications = Optional.ofNullable(source.recommendations.get().notifications())
                                        .map(map -> List.copyOf(map.values()))
                                        .orElse(Collections.emptyList());


                                Map<String, TimestampData> dataMap = source.recommendations().get().data();
                                if (dataMap == null || dataMap.isEmpty()) {
                                    return new FinalCostResult(
                                            source.parentNamespace(),
                                            source.sourceName(),
                                            experimentName,
                                            experimentType,
                                            notifications,
                                            null,
                                            Collections.emptyList() // No cost recommendations
                                    );
                                }

                                TimestampData timestampData = dataMap.values().iterator().next();
                                ResourceGroup currentUsage = timestampData.current();
                                Map<String, RecommendationTerm> recommendationTerms = timestampData.recommendationTerms();
                                if (recommendationTerms == null) {
                                    return new FinalCostResult(
                                            source.parentNamespace(),
                                            source.sourceName(),
                                            experimentName,
                                            experimentType,
                                            notifications,
                                            currentUsage,
                                            Collections.emptyList() // No currentUsage
                                    );
                                }

                                List<CostRecommendation> costRecs = recommendationTerms.entrySet().stream()
                                        .map(termEntry -> {
                                            String term = termEntry.getKey();
                                            RecommendationTerm recommendationTerm = termEntry.getValue();

                                            Map<String, RecommendationEngine> engines = Optional.ofNullable(recommendationTerm.recommendationEngines()).orElse(Collections.emptyMap());
                                            RecommendationEngine costEngine = engines.get("cost");

                                            List<Notification> costNotifications = Optional.ofNullable(costEngine)
                                                    .map(RecommendationEngine::notifications)
                                                    .map(map -> List.copyOf(map.values()))
                                                    .orElse(Collections.emptyList());

                                            return new CostRecommendation(
                                                    term,
                                                    recommendationTerm.durationInHours(),
                                                    Optional.ofNullable(costEngine).map(RecommendationEngine::config),
                                                    Optional.ofNullable(costEngine).map(RecommendationEngine::variation),
                                                    Optional.of(costNotifications)
                                            );
                                        })
                                        .collect(Collectors.toList());

                                // Use the data from the unified 'source' object
                                return new FinalCostResult(
                                        source.parentNamespace(),
                                        source.sourceName(),
                                        experimentName,
                                        experimentType,
                                        notifications,
                                        currentUsage,
                                        costRecs
                                );
                            })
                            .filter(java.util.Objects::nonNull)
                            .forEach(allFinalResults::add);
                }
            }

            return objectMapper.writeValueAsString(allFinalResults);

        } catch (Exception e) {
            return "{\"error\": \"An unexpected error occurred: " + e.getMessage() + "\"}";
        }
    }


    @Tool(description = "Retrieves cost recommendations for Idle workloads that have a specific notification with code 323001.")
    public String getIdleWorkloads() {
        try {
            List<Recommendations> apiResponse = apiClient.getAllRecommendations();
            List<FinalCostResult> filteredResults = new ArrayList<>();

            // 1. Loop through each Recommendation
            for (Recommendations recommendations : Optional.ofNullable(apiResponse).orElse(Collections.emptyList())) {

                // 2. Loop through each KubernetesObject
                for (KubernetesObject k8sObject : Optional.ofNullable(recommendations.kubernetesObjects()).orElse(Collections.emptyList())) {

                    // 3. Create a unified list of sources from containers and namespaces
                    List<RecommendationSource> sources = new ArrayList<>();
                    k8sObject.containers().orElse(Collections.emptyList())
                            .forEach(c -> sources.add(new RecommendationSource(k8sObject.namespace(), Optional.of(c.containerName()), c.recommendations())));
                    k8sObject.namespaces().stream()
                            .forEach(n -> sources.add(new RecommendationSource(n.namespace(), Optional.empty(), n.recommendations())));

                    // 4. Loop through each source (container or namespace)
                    for (RecommendationSource source : sources) {
                        if (source.recommendations().isEmpty()) continue;

                        List<Notification> notifications = Optional.ofNullable(source.recommendations.get().notifications())
                                .map(map -> List.copyOf(map.values()))
                                .orElse(Collections.emptyList());

                        Map<String, TimestampData> dataMap = source.recommendations().get().data();
                        if (dataMap == null || dataMap.isEmpty()) continue;

                        TimestampData timestampData = dataMap.values().iterator().next();
                        Map<String, RecommendationTerm> recommendationTerms = timestampData.recommendationTerms();
                        if (recommendationTerms == null) continue;

                        // 5. Filter the terms to find only those with the specific Idle notification - "323001"
                        List<CostRecommendation> matchingRecs = recommendationTerms.entrySet().stream()
                                .filter(termEntry -> {
                                    RecommendationEngine costEngine = Optional.ofNullable(termEntry.getValue().recommendationEngines())
                                            .orElse(Collections.emptyMap()).get("cost");

                                    if (costEngine == null || costEngine.notifications() == null) return false;

                                    // The filtering condition
                                    Notification notice = costEngine.notifications().get("323001");
                                    return notice != null && "notice".equals(notice.type());
                                })
                                .map(termEntry -> {
                                    // Map the matching entry to a CostRecommendation object
                                    RecommendationEngine costEngine = termEntry.getValue().recommendationEngines().get("cost");
                                    List<Notification> costNotifications = Optional.ofNullable(costEngine)
                                            .map(RecommendationEngine::notifications)
                                            .map(map -> List.copyOf(map.values()))
                                            .orElse(Collections.emptyList());


                                    return new CostRecommendation(
                                            termEntry.getKey(),
                                            termEntry.getValue().durationInHours(),
                                            Optional.ofNullable(costEngine).map(RecommendationEngine::config),
                                            Optional.ofNullable(costEngine).map(RecommendationEngine::variation),
                                            Optional.of(costNotifications) // Add the extracted notifications here
                                    );
                                })
                                .collect(Collectors.toList());

                        // 6. If we found any matches, create a result object and add it to our final list
                        if (!matchingRecs.isEmpty()) {
                            filteredResults.add(new FinalCostResult(
                                    source.parentNamespace(),
                                    source.sourceName(),
                                    recommendations.experimentName(),
                                    recommendations.experimentType(),
                                    notifications,
                                    timestampData.current(),
                                    matchingRecs
                            ));
                        }
                    }
                }
            }

            return objectMapper.writeValueAsString(filteredResults);

        } catch (Exception e) {
            return "{\"error\": \"An unexpected error occurred: " + e.getMessage() + "\"}";
        }
    }
}
