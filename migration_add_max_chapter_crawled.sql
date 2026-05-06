-- Migration: Add max_chapter_crawled column to manga table
-- Run this if you already have an existing database

ALTER TABLE manga ADD COLUMN IF NOT EXISTS max_chapter_crawled INTEGER DEFAULT 0;
