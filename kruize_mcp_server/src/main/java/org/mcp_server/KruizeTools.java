package org.mcp_server;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkiverse.mcp.server.Tool;
import io.quarkiverse.mcp.server.ToolArg;
import org.eclipse.microprofile.rest.client.inject.RestClient;
import jakarta.inject.Inject;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;
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
    public String getAllRecommendations() {
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

    @Tool(description = "Retrieves available cost recommendations for the specified experiment name.")
    public String getCostOptimizedRecommendations(
            @ToolArg(description = "The name of the experiment to get recommendations for.") String experiment_name) {
        try {
            List<Recommendations> apiResponse = apiClient.getCostOptimizedRecommendations(experiment_name);

            List<FinalCostResult> allFinalResults = apiResponse.stream()
                    .flatMap(experiment -> Optional.ofNullable(experiment.kubernetesObjects()).orElse(Collections.emptyList()).stream())
                    .flatMap(kubeObject -> {
                        // Create a stream of RecommendationSource from containers
                        // Stream from containers
                        Stream<RecommendationSource> fromContainers = kubeObject.containers()
                                .orElse(Collections.emptyList()).stream()
                                .map(c -> new RecommendationSource(
                                        kubeObject.namespace(),
                                        Optional.of(c.containerName()),
                                        c.recommendations()
                                ));

                        // Stream from namespaces
                        Stream<RecommendationSource> fromNamespaces = kubeObject.namespaces().stream()
                                .map(n -> new RecommendationSource(
                                        n.namespace(),
                                        Optional.empty(),
                                        n.recommendations()
                                ));

                        // Combine both streams into one
                        return Stream.concat(fromContainers, fromNamespaces);
                    })
                    .map(source -> {
                        // Now, process the unified 'source' object
                        if (source.recommendations().isEmpty()) return null;

                        Map<String, TimestampData> dataMap = source.recommendations().get().data();
                        if (dataMap == null || dataMap.isEmpty()) return null;

                        TimestampData timestampData = dataMap.values().iterator().next();
                        ResourceGroup currentUsage = timestampData.current();
                        Map<String, RecommendationTerm> recommendationTerms = timestampData.recommendationTerms();
                        if (recommendationTerms == null) return null;

                        List<CostRecommendation> costRecs = recommendationTerms.entrySet().stream()
                                .map(termEntry -> {
                                    String term = termEntry.getKey();
                                    RecommendationTerm recommendationTerm = termEntry.getValue();

                                    Map<String, RecommendationEngine> engines = Optional.ofNullable(recommendationTerm.recommendationEngines()).orElse(Collections.emptyMap());
                                    RecommendationEngine costEngine = engines.get("cost");

                                    return new CostRecommendation(
                                            term,
                                            recommendationTerm.durationInHours(),
                                            Optional.ofNullable(costEngine).map(RecommendationEngine::config),
                                            Optional.ofNullable(costEngine).map(RecommendationEngine::variation)
                                    );
                                })
                                .collect(Collectors.toList());

                        // Use the data from the unified 'source' object
                        return new FinalCostResult(source.parentNamespace(), source.sourceName(), currentUsage, costRecs);
                    })
                    .filter(java.util.Objects::nonNull)
                    .collect(Collectors.toList());

            return objectMapper.writeValueAsString(allFinalResults);

        } catch (Exception e) {
            e.printStackTrace();
            return "{\"error\": \"An unexpected error occurred: " + e.getMessage() + "\"}";
        }
    }
}
