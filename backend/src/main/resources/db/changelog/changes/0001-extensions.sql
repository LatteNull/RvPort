--liquibase formatted sql

--changeset rvport:0001-extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
