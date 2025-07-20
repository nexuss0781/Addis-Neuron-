use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use std::sync::{Arc, Mutex};
use actix_web_prom::PrometheusMetricsBuilder;

// Declare the modules
mod lve;
mod hsm;
mod ace;
mod nlse_core;

use nlse_core::{
    storage_manager::StorageManager,
    decay_agent::DecayAgent,
    query_engine::{QueryEngine, ExecutionPlan},
};


// --- The shared application state ---
struct AppState {
    query_engine: Mutex<QueryEngine>,
}


// --- API Handlers ---
#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json("{\"engine_status\": \"nominal\"}")
}

#[post("/validate")]
async fn validate_logic(request: web::Json<lve::LveRequest>) -> impl Responder {
    let validation_result = lve::validate_contradiction(&request.into_inner());
    HttpResponse::Ok().json(validation_result)
}

#[post("/hypothesize")]
async fn hypothesize_logic(request: web::Json<hsm::HsmRequest>) -> impl Responder {
    let reasoning_result = hsm::reason_hypothetically(&request.into_inner());
    HttpResponse::Ok().json(reasoning_result)
}

#[post("/ace/run-compression")]
async fn run_ace_compression(request: web::Json<ace::AceRequest>) -> impl Responder {
    let compression_result = ace::run_compression_analysis(&request.into_inner());
    HttpResponse::Ok().json(compression_result)
}

// --- NEW ENDPOINT for the Query Engine ---
#[post("/nlse/execute-plan")]
async fn execute_nlse_plan(
    plan: web::Json<ExecutionPlan>,
    data: web::Data<AppState>,
) -> impl Responder {
    // Lock the query engine to handle one plan at a time for now
    let engine = data.query_engine.lock().unwrap();
    let result = engine.execute(plan.into_inner());
    HttpResponse::Ok().json(result)
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    println!("🚀 Rust Logic Engine starting...");

    // 1. Initialize the Storage Manager. We'll use a directory in the root for persistence.
    // The Arc<Mutex> allows safe sharing across threads.
    let storage_manager = Arc::new(Mutex::new(
        StorageManager::new("./nlse_data").expect("Failed to initialize Storage Manager")
    ));

    // 2. Start the autonomous DecayAgent, giving it access to the StorageManager.
    DecayAgent::start(Arc::clone(&storage_manager));
    
    // 3. Initialize the Query Engine with the same StorageManager.
    let query_engine = QueryEngine::new(Arc::clone(&storage_manager));

    // 4. Create the shared state for the Actix web server.
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
            .app_data(app_state.clone()) // Make the state available to all handlers
            .wrap(prometheus.clone())
            .service(health)
            .service(validate_logic)
            .service(hypothesize_logic)
            .service(run_ace_compression)
            .service(execute_nlse_plan) // Register the new endpoint
    })
    .bind(("0.0.0.0", 8000))?
    .run()
    .await
}