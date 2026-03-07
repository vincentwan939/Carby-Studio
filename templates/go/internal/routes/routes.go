package routes

import (
	"{{PROJECT_NAME}}/internal/handlers"

	"github.com/gin-gonic/gin"
)

// Setup configures all routes
func Setup(router *gin.Engine) {
	// Health check (required for load balancers)
	router.GET("/health", handlers.HealthCheck)

	// Root endpoint
	router.GET("/", handlers.Root)

	// TODO: Add your routes here
	// Example:
	// api := router.Group("/api/v1")
	// {
	//     api.GET("/users", handlers.GetUsers)
	//     api.POST("/users", handlers.CreateUser)
	// }
}
