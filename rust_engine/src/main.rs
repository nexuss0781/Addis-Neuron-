use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use serde::{Deserialize, Serialize};
use actix_web_prom::PrometheusMetricsBuilder;

// Declare the modules for different brain engines
mod lve;
mod hsm;
mod ace; // <-- MODIFICATION: Add ace module
mod nlse_core;

#[derive(Serialize)]
struct HealthResponse {
    engine_status: String,
}

// Health check endpoint
#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json(HealthResponse {
        engine_status: "nominal".to_string(),
    })
}

// LVE endpoint
#[post("/validate")]
async fn validate_logic(request: web::Json<lve::LveRequest>) -> impl Responder {
    let validation_result = lve::validate_contradiction(&request.into_inner());
    HttpResponse::Ok().json(validation_result)
}

// HSM endpoint
#[post("/hypothesize")]
async fn hypothesize_logic(request: web::Json<hsm::HsmRequest>) -> impl Responder {
    let reasoning_result = hsm::reason_hypothetically(&request.into_inner());
    HttpResponse::Ok().json(reasoning_result)
}

// --- NEW ENDPOINT for the ACE ---
#[post("/ace/run-compression")]
async fn run_ace_compression(request: web::Json<ace::AceRequest>) -> impl Responder {
    // Delegate to the ACE module
    let compression_result = ace::run_compression_analysis(&request.into_inner());
    HttpResponse::Ok().json(compression_result)
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 Rust Logic Engine starting...");

    let prometheus = PrometheusMetricsBuilder::new("logical_engine")
        .endpoint("/metrics")
        .build()
        .unwrap();

    HttpServer::new(move || {
        App::new()
            .wrap(prometheus.clone())
            .service(health)
            .service(validate_logic)
            .service(hypothesize_logic)
            .service(run_ace_compression) // <-- MODIFICATION: Register the new ACE service
    })
    .bind(("0.0.0.0", 8000))?
    .run()
    .await
}
