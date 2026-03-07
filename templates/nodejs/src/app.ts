/**
 * Express application configuration.
 */

import express, { Application, Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';

import { config, isDevelopment } from './config';
import { errorHandler } from './middleware/error';
import routes from './routes';

export function createApp(): Application {
  const app = express();

  // Security middleware
  app.use(helmet());
  app.use(cors({
    origin: config.corsOrigin,
    credentials: true,
  }));

  // Logging
  app.use(morgan(isDevelopment ? 'dev' : 'combined'));

  // Body parsing
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  // Routes
  app.use('/', routes);

  // Error handling (must be last)
  app.use(errorHandler);

  return app;
}
