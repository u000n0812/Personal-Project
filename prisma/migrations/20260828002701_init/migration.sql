-- CreateEnum
CREATE TYPE "EntryType" AS ENUM ('DREAM', 'TAROT');

-- CreateTable
CREATE TABLE "Entry" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "type" "EntryType" NOT NULL,
    "dreamText" TEXT,
    "mood" TEXT,
    "symbols" JSONB,
    "advice" TEXT,
    "title" TEXT,
    "cardName" TEXT,
    "cardKeyword" TEXT,
    "reversed" BOOLEAN,
    "tarotAdvice" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Entry_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Entry_userId_createdAt_idx" ON "Entry"("userId", "createdAt");
