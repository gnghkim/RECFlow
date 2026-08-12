-- CreateEnum
CREATE TYPE "MarketArea" AS ENUM ('LAND', 'JEJU', 'TOTAL');

-- CreateEnum
CREATE TYPE "CollectionJobType" AS ENUM ('SCHEDULED', 'RECHECK', 'BACKFILL', 'MANUAL', 'GAP_SCAN');

-- CreateEnum
CREATE TYPE "CollectionStatus" AS ENUM ('SUCCESS', 'PARTIAL', 'NO_DATA', 'FAILED');

-- CreateTable
CREATE TABLE "rec_market" (
    "id" SERIAL NOT NULL,
    "trade_date" DATE NOT NULL,
    "market_area" "MarketArea" NOT NULL,
    "trade_count" INTEGER,
    "volume" DECIMAL(14,2),
    "avg_price" DECIMAL(12,2),
    "high_price" DECIMAL(12,2),
    "low_price" DECIMAL(12,2),
    "close_price" DECIMAL(12,2),
    "trade_amount" DECIMAL(18,2),
    "source" VARCHAR(32) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "rec_market_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "rec_market_raw" (
    "id" SERIAL NOT NULL,
    "trade_date" DATE NOT NULL,
    "endpoint" VARCHAR(255) NOT NULL,
    "http_status" INTEGER NOT NULL,
    "payload" JSONB NOT NULL,
    "fetched_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "collection_run_id" INTEGER,

    CONSTRAINT "rec_market_raw_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "collection_runs" (
    "id" SERIAL NOT NULL,
    "job_type" "CollectionJobType" NOT NULL,
    "target_date" DATE,
    "status" "CollectionStatus" NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "rows_upserted" INTEGER NOT NULL DEFAULT 0,
    "error_message" TEXT,
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finished_at" TIMESTAMP(3),

    CONSTRAINT "collection_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "plants" (
    "id" SERIAL NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "location" VARCHAR(200),
    "capacity_kw" DECIMAL(12,2),
    "operation_date" DATE,
    "rec_weight" DECIMAL(4,2),
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "plants_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "rec_inventory" (
    "id" SERIAL NOT NULL,
    "plant_id" INTEGER NOT NULL,
    "issue_date" DATE NOT NULL,
    "rec_quantity" DECIMAL(14,2) NOT NULL,
    "expired_at" DATE,
    "memo" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "rec_inventory_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "rec_sales" (
    "id" SERIAL NOT NULL,
    "plant_id" INTEGER NOT NULL,
    "sale_date" DATE NOT NULL,
    "quantity" DECIMAL(14,2) NOT NULL,
    "unit_price" DECIMAL(12,2) NOT NULL,
    "sale_amount" DECIMAL(18,2) NOT NULL,
    "buyer" VARCHAR(120),
    "memo" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "rec_sales_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "price_targets" (
    "id" SERIAL NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "target_price" DECIMAL(12,2) NOT NULL,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "price_targets_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "rec_market_trade_date_idx" ON "rec_market"("trade_date");

-- CreateIndex
CREATE UNIQUE INDEX "rec_market_trade_date_market_area_key" ON "rec_market"("trade_date", "market_area");

-- CreateIndex
CREATE INDEX "rec_market_raw_trade_date_idx" ON "rec_market_raw"("trade_date");

-- CreateIndex
CREATE INDEX "collection_runs_target_date_idx" ON "collection_runs"("target_date");

-- CreateIndex
CREATE INDEX "collection_runs_started_at_idx" ON "collection_runs"("started_at");

-- CreateIndex
CREATE INDEX "rec_inventory_plant_id_idx" ON "rec_inventory"("plant_id");

-- CreateIndex
CREATE INDEX "rec_inventory_issue_date_idx" ON "rec_inventory"("issue_date");

-- CreateIndex
CREATE INDEX "rec_sales_plant_id_idx" ON "rec_sales"("plant_id");

-- CreateIndex
CREATE INDEX "rec_sales_sale_date_idx" ON "rec_sales"("sale_date");

-- AddForeignKey
ALTER TABLE "rec_market_raw" ADD CONSTRAINT "rec_market_raw_collection_run_id_fkey" FOREIGN KEY ("collection_run_id") REFERENCES "collection_runs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "rec_inventory" ADD CONSTRAINT "rec_inventory_plant_id_fkey" FOREIGN KEY ("plant_id") REFERENCES "plants"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "rec_sales" ADD CONSTRAINT "rec_sales_plant_id_fkey" FOREIGN KEY ("plant_id") REFERENCES "plants"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
