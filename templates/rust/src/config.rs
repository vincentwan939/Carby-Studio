use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub app_name: String,
    pub version: String,
    pub port: u16,
    pub env: String,
    pub database_url: String,
    pub jwt_secret: String,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            app_name: env::var("APP_NAME").unwrap_or_else(|_| "{{PROJECT_NAME}}".to_string()),
            version: env!("CARGO_PKG_VERSION").to_string(),
            port: env::var("PORT")
                .ok()
                .and_then(|p| p.parse().ok())
                .unwrap_or(3000),
            env: env::var("ENV").unwrap_or_else(|_| "development".to_string()),
            database_url: env::var("DATABASE_URL")
                .unwrap_or_else(|_| "postgres://localhost:5432/{{PROJECT_NAME}}".to_string()),
            jwt_secret: env::var("JWT_SECRET")
                .unwrap_or_else(|_| "change-me-in-production".to_string()),
        }
    }

    pub fn is_development(&self) -> bool {
        self.env == "development"
    }

    pub fn is_production(&self) -> bool {
        self.env == "production"
    }
}
