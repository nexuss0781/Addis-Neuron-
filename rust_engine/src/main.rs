use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use std::sync::{Arc, Mutex};
use actix_web_prom::PrometheusMetricsBuilder;

// Declare only the modules that are still used
mod ace;        // Still used for ace::AceRequest
mod hsm;     // Logic moved to nlse_core::query_engine, only HsmRequest is needed
mod lve;     // Logic moved to nlse_core::query_engine, only LveRequest is needed
mod nlse_core;  // Core library

// Bring specific items into scope from nlse_core
use nlse_core::storage_manager::StorageManager;
use nlse_core::decay_agent::DecayAgent;
use nlse_core::query_engine::{QueryEngine, ExecutionPlan}; // Correct path for QueryEngine and ExecutionPlan

// Bring in request/response types from now unused modules if needed
// use hsm::HsmRequest; // Only used for the request struct
// use lve::LveRequest; // Only used for the request struct
use ace::AceRequest; // Only used for the request struct

// --- The shared application state ---
// Needs to hold the QueryEngine
struct AppState { query_engine: Mutex<QueryEngine>, }

// --- API Handlers ---
#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json("{\"engine_status\": \"nominal\"}")
}

// The /validate endpoint and its handler `validate_logic` are DELETED as the LVE is now native.
// #[post("/validate")]
// async fn validate_logic(request: web::Json<lve::LveRequest>) -> impl Responder { ... }

// The /hypothesize endpoint and its handler `hypothesize_logic` are DELETED as the HSM is now native.
// We keep the function here but it will not be served
#[post("/hypothesize")]
async fn hypothesize_logic(request: web::Json<HsmRequest>) -> impl Responder {
    // This logic is now handled natively by QueryEngine, so this endpoint is obsolete.
    HttpResponse::BadRequest().json("HSM logic is now integrated into /nlse/execute-plan. This endpoint is deprecated.")
}

#[post("/ace/run-compression")]
async fn run_ace_compression(request: web::Json<AceRequest>) -> impl Responder {
    let compression_result = ace::run_compression_analysis(&request.into_inner());
    HttpResponse::Ok().json(compression_result)
}

#[post("/nlse/execute-plan")]
async fn execute_nlse_plan(
    plan: web::Json<ExecutionPlan>,
    data: web::Data<AppState>,
) -> impl Responder {
    let engine = data.query_engine.lock().unwrap();
    let result = engine.execute(plan.into_inner());
    HttpResponse::Ok().json(result)
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 Rust Logic Engine starting...");

    let storage_manager = Arc::new(Mutex::new(
        StorageManager::new("./nlse_data").expect("Failed to initialize Storage Manager")
    ));

    DecayAgent::start(Arc::clone(&storage_manager));
    
    let query_engine = QueryEngine::new(Arc::clone(&storage_manager));
    let app_state = web::Data::new(AppState {
        query_engine: Mutex::new(query_engine),
    });

    let prometheus = PrometheusMetricsBuilder::new("logical_engine")
        .endpoint("/metrics")
        .build()
        .unwrap();

    println!("✅ NLSE and services initialized. Starting web server...");

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(prometheus.clone())
            .service(health)
            // .service(validate_logic) // Remove as LVE is now native
            .service(hypothesize_logic) // Keep as deprecated endpoint
            .service(run_ace_compression)
            .service(execute_nlse_plan)
    })
    .bind(("0.0.0.0", 8000))?
    .run()
    .await
}