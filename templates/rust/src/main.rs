use axum::{
    routing::get,
    Router,
};
use std::net::SocketAddr;
use tokio::signal;
use tracing::{info, warn};

mod config;
mod handlers;
mod routes;

use config::Config;

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    // Load configuration
    let config = Config::from_env();
    
    info!("🚀 Starting {} v{}", config.app_name, config.version);
    info!("📊 Environment: {}", config.env);

    // Build router
    let app = routes::create_router();

    // Bind to address
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    info!("🌐 Listening on http://{}", addr);

    // Start server with graceful shutdown
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .with_graceful_shutdown(shutdown_signal())
        .await
        .unwrap();
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("Failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("Failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            warn!("Received Ctrl+C, shutting down gracefully");
        },
        _ = terminate => {
            warn!("Received SIGTERM, shutting down gracefully");
        },
    }
}
