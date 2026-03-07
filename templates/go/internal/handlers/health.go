package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// HealthResponse represents health check response
type HealthResponse struct {
	Status    string    `json:"status"`
	Version   string    `json:"version"`
	Service   string    `json:"service"`
	Timestamp time.Time `json:"timestamp"`
}

// HealthCheck handles health check requests
func HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, HealthResponse{
		Status:    "healthy",
		Version:   "0.1.0",
		Service:   "{{PROJECT_NAME}}",
		Timestamp: time.Now().UTC(),
	})
}

// Root handles root endpoint
func Root(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"name":        "{{PROJECT_NAME}}",
		"version":     "0.1.0",
		"description": "{{PROJECT_DESCRIPTION}}",
	})
}
