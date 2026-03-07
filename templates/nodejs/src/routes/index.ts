/**
 * Main router configuration.
 */

import { Router } from 'express';
import { healthCheck, root } from '../controllers/health';

const router = Router();

// Health check endpoint (required for load balancers)
router.get('/health', healthCheck);

// Root endpoint
router.get('/', root);

// TODO: Add your routes here
// Example:
// import { userRouter } from './users';
// router.use('/users', userRouter);

export default router;
