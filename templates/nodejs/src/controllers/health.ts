/**
 * Health check controller.
 */

import { Request, Response } from 'express';
import { config } from '../config';

export const healthCheck = (_req: Request, res: Response): void => {
  res.json({
    status: 'healthy',
    version: '0.1.0',
    service: '{{PROJECT_NAME}}',
    timestamp: new Date().toISOString(),
  });
};

export const root = (_req: Request, res: Response): void => {
  res.json({
    name: '{{PROJECT_NAME}}',
    version: '0.1.0',
    description: '{{PROJECT_DESCRIPTION}}',
    environment: config.env,
  });
};
