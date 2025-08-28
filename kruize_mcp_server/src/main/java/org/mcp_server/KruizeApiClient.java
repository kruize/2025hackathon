package org.mcp_server;

import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import java.util.List;
import org.mcp_server.ApiResponseRecords.Experiment;
import org.mcp_server.ApiResponseRecords.Recommendations;

@RegisterRestClient // No hardcoded URL here!
public interface KruizeApiClient {

    @GET
    @Path("/listExperiments")
    List<Experiment> getAllExperiments();

    @GET
    @Path("/listRecommendations")
    List<Recommendations> listRecommendations();

//    @GET
//    @Path("/listRecommendations")
//    List<Experiment> listRecommendations(@QueryParam("experiment_name") String experiment_name);
}