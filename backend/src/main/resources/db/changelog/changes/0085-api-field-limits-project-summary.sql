--liquibase formatted sql

--changeset rvport:0085-users-username-length
ALTER TABLE users
    ADD CONSTRAINT users_username_length_chk CHECK (char_length(username) <= 64);
