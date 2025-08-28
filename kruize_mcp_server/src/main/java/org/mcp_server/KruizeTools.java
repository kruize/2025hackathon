package org.mcp_server;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkiverse.mcp.server.Tool;
import org.eclipse.microprofile.rest.client.inject.RestClient;
import jakarta.inject.Inject;
import java.util.List;
import java.util.stream.Collectors;
import org.mcp_server.ApiResponseRecords.Experiment;
import org.mcp_server.ApiResponseRecords.Recommendations;

public class KruizeTools {

    @Inject
    @RestClient
    KruizeApiClient apiClient; // Inject the client you defined

    @Inject // 1. Inject the JSON Mapper
    ObjectMapper objectMapper;

    @Tool(description = "Retrieves a list of all available experiments in text format.")
    public String listAllExperimentsText() {
        try {
            // 1. Call your deployed application via the API client
            List<Experiment> experiments = apiClient.getAllExperiments();

            if (experiments == null || experiments.isEmpty()) {
                return "No experiments were found.";
            }

            // 2. Format the result into a clean, human-readable string
            return "Here are the available experiments:\n" +
                    experiments.stream()
                            .map(exp -> String.format("- ID: %s, Name: %s, Status: %s, Experiment type:%s, Mode %s, Cluster type:%s", exp.experiment_id(), exp.experiment_name(), exp.status(), exp.experiment_type(), exp.mode(), exp.target_cluster()))
                            .collect(Collectors.joining("\n"));

        } catch (Exception e) {
            return "Sorry, unable to retrieve the experiments. There might be a connection issue.";
        }
    }

    @Tool(description = "Retrieves a list of all available experiments in JSON format.")
    public String listAllExperiments() {
        try {
            List<Experiment> experiments = apiClient.getAllExperiments();

            if (experiments == null || experiments.isEmpty()) {
                // Return a valid empty JSON array
                return "[]";
            }

            // 2. Serialize the list of experiments into a JSON string
            return objectMapper.writeValueAsString(experiments);

        } catch (JsonProcessingException e) {
            // Handle serialization errors
            return "{\"error\": \"Failed to serialize experiment data to JSON.\"}";
        } catch (Exception e) {
            // Handle API connection errors
            return "{\"error\": \"Failed to retrieve experiments from the API.\"}";
        }
    }

    @Tool(description = "Retrieves a list of all available recommendations.")
    public String listRecommendations() {
        try {
            List<Recommendations> recommendationsList = apiClient.listRecommendations();

            if (recommendationsList == null || recommendationsList.isEmpty()) {
                // Return a valid empty JSON array
                return "[]";
            }

            // 2. Serialize the list of experiments into a JSON string
            return objectMapper.writeValueAsString(recommendationsList);

        } catch (JsonProcessingException e) {
            // Handle serialization errors
            return "{\"error\": \"Failed to serialize recommendation data to JSON.\"}";
        } catch (Exception e) {
            // Handle API connection errors
            return "{\"error\": \"Failed to retrieve recommendations from the API.\"}" + e.getMessage();
        }
    }
}
