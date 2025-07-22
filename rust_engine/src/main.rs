use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};
use std::sync::{Arc, Mutex};
use actix_web_prom::PrometheusMetricsBuilder;

mod lve;
mod hsm;
mod ace;
mod nlse_core;

use nlse_core::{storage_manager::StorageManager, decay_agent::DecayAgent, query_engine::{QueryEngine, ExecutionPlan}};

struct AppState { query_engine: Mutex<QueryEngine>, }

#[get("/health")]
async fn health() -> impl Responder { HttpResponse::Ok().json("{\"engine_status\": \"nominal\"}") }

// --- THIS FUNCTION IS NOW DELETED ---
// #[post("/validate")]
// async fn validate_logic(request: web::Json<lve::LveRequest>) -> impl Responder { ... }

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

#[post("/nlse/execute-plan")]
async fn execute_nlse_plan(plan: web::Json<ExecutionPlan>, data: web::Data<AppState>) -> impl Responder {
    let engine = data.query_engine.lock().unwrap();
    let result = engine.execute(plan.into_inner());
    HttpResponse::Ok().json(result)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    // ... (main function setup remains the same)
    let storage_manager = Arc::new(Mutex::new(StorageManager::new("./nlse_data").expect("...")));
    DecayAgent::start(Arc::clone(&storage_manager));
    let query_engine = QueryEngine::new(Arc::clone(&storage_manager));
    let app_state = web::Data::new(AppState { query_engine: Mutex::new(query_engine) });
    let prometheus = PrometheusMetricsBuilder::new("logical_engine").endpoint("/metrics").build().unwrap();

    HttpServer::new(move || {
        App::new()
            .app_data(app_state.clone())
            .wrap(prometheus.clone())
            .service(health)
            // --- THE /validate SERVICE IS NOW REMOVED ---
            .service(hypothesize_logic)
            .service(run_ace_compression)
            .service(execute_nlse_plan)
    })
    .bind(("0.0.0.0", 8000))?.run().await
}