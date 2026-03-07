/**
 * Application configuration.
 * Loads from environment variables with sensible defaults.
 */

export interface Config {
  env: string;
  port: number;
  host: string;
  databaseUrl: string;
  jwtSecret: string;
  corsOrigin: string;
}

export const config: Config = {
  env: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT || '3000', 10),
  host: process.env.HOST || '0.0.0.0',
  databaseUrl: process.env.DATABASE_URL || 'postgresql://localhost:5432/{{PROJECT_NAME}}',
  jwtSecret: process.env.JWT_SECRET || 'change-me-in-production',
  corsOrigin: process.env.CORS_ORIGIN || '*',
};

export const isDevelopment = config.env === 'development';
export const isProduction = config.env === 'production';
export const isTest = config.env === 'test';
