/**
 * Application entry point.
 */

import { createApp } from './app';
import { config } from './config';

const app = createApp();

const server = app.listen(config.port, config.host, () => {
  console.log(`🚀 Server running on http://${config.host}:${config.port}`);
  console.log(`📊 Environment: ${config.env}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully');
  server.close(() => {
    console.log('Process terminated');
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully');
  server.close(() => {
    console.log('Process terminated');
  });
});
