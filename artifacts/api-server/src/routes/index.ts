import { Router, type IRouter } from "express";
import healthRouter from "./health";
import nekoDashboardRouter from "./neko-dashboard";

const router: IRouter = Router();

router.use(healthRouter);
router.use("/dashboard-api", nekoDashboardRouter);

export default router;
