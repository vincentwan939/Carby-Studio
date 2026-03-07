package config

import (
	"os"
)

// Config holds application configuration
type Config struct {
	Port        string
	Env         string
	DatabaseURL string
	JWTSecret   string
}

// Load loads configuration from environment variables
func Load() *Config {
	return &Config{
		Port:        getEnv("PORT", "8080"),
		Env:         getEnv("ENV", "development"),
		DatabaseURL: getEnv("DATABASE_URL", "postgresql://localhost:5432/{{PROJECT_NAME}}"),
		JWTSecret:   getEnv("JWT_SECRET", "change-me-in-production"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// IsDevelopment returns true if running in development mode
func (c *Config) IsDevelopment() bool {
	return c.Env == "development"
}

// IsProduction returns true if running in production mode
func (c *Config) IsProduction() bool {
	return c.Env == "production"
}
