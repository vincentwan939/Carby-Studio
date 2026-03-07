use axum::{Json, http::StatusCode};
use chrono::Utc;
use serde::Serialize;

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub service: String,
    pub timestamp: String,
}

pub async fn health_check() -> (StatusCode, Json<HealthResponse>) {
    let response = HealthResponse {
        status: "healthy".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        service: "{{PROJECT_NAME}}".to_string(),
        timestamp: Utc::now().to_rfc3339(),
    };
    (StatusCode::OK, Json(response))
}

#[derive(Serialize)]
pub struct RootResponse {
    pub name: String,
    pub version: String,
    pub description: String,
}

pub async fn root() -> Json<RootResponse> {
    Json(RootResponse {
        name: "{{PROJECT_NAME}}".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        description: "{{PROJECT_DESCRIPTION}}".to_string(),
    })
}
