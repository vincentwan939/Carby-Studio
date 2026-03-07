use axum::{
    routing::get,
    Router,
};

use crate::handlers::health;

pub fn create_router() -> Router {
    Router::new()
        .route("/health", get(health::health_check))
        .route("/", get(health::root))
    // TODO: Add your routes here
    // .route("/users", get(handlers::users::list_users))
}
