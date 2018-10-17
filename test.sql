DROP DATABASE IF EXISTS pypatrol_test;

CREATE DATABASE pypatrol_test;

\c pypatrol_test;

-- Table: alert_contact
CREATE TABLE alert_contact (
    id int  NOT NULL,
    user_id int  NOT NULL,
    alert_type int  NOT NULL,
    value text  NOT NULL,
    CONSTRAINT alert_contact_pk PRIMARY KEY (id)
);

INSERT INTO alert_contact (id, user_id, alert_type, value)
VALUES (1, 1, 1, 'mason@rowe.sh');

-- Table: alert_types
CREATE TABLE alert_types (
    id int  NOT NULL,
    name text  NOT NULL,
    CONSTRAINT alert_types_pk PRIMARY KEY (id)
);

INSERT INTO alert_types (id, name)
VALUES (1, 'Email');

-- Table: cert_service
CREATE TABLE cert_service (
    id int  NOT NULL,
    service_id int  NOT NULL,
    hostname text  NOT NULL,
    buffer int  NOT NULL,
    CONSTRAINT cert_service_pk PRIMARY KEY (id)
);

INSERT INTO cert_service (id, service_id, hostname, buffer)
VALUES (1, 4, 'www.google.com', 14);

-- Table: http_service
CREATE TABLE http_service (
    id int  NOT NULL,
    service_id int  NOT NULL,
    hostname text  NOT NULL,
    redirects boolean  NOT NULL,
    check_string boolean  NOT NULL,
    keywords text  NULL,
    CONSTRAINT http_service_pk PRIMARY KEY (id)
);

INSERT INTO http_service (id, service_id, hostname, redirects, check_string, keywords)
VALUES (1, 3, 'https://www.google.com', FALSE, FALSE, NULL);

-- Table: ip_port_service
CREATE TABLE ip_port_service (
    id SERIAL PRIMARY KEY,
    service_id int  NOT NULL,
    ip_host text  NOT NULL,
    port int  NULL
    --CONSTRAINT ip_port_service_pk PRIMARY KEY (id)
);

INSERT INTO ip_port_service (service_id, ip_host, port)
VALUES
  (1, '8.8.8.8', NULL),
  (2, '2001:4860:4860::8888', NULL),
  (5, '8.8.8.8', 53),
  (6, '74.91.113.28', 27003);

-- Table: service
CREATE TABLE service (
    id SERIAL PRIMARY KEY,
    user_id int  NOT NULL,
    active boolean  NOT NULL,
    type int  NOT NULL,
    name text NOT NULL,
    status text  NOT NULL,
    status_desc text  NULL,
    error_state boolean NOT NULL,
    interval int NOT NULL,
    last_check_time timestamp  NOT NULL,
    status_change_time timestamp  NOT NULL
    --CONSTRAINT service_pk PRIMARY KEY (id)
);

INSERT INTO service (user_id, active, type, name, status, status_desc, error_state, interval, last_check_time, status_change_time)
VALUES
  (1, TRUE, 1, 'PING TEST', 'offline', NULL, FALSE, 60, NOW(), NOW()),
  (1, TRUE, 2, 'PINGv6 TEST', 'online', NULL, FALSE, 60, NOW(), NOW()),
  (1, TRUE, 3, 'HTTP TEST', 'online', '200', FALSE, 60, NOW(), NOW()),
  (1, TRUE, 4, 'SSL TEST', 'valid', NULL, FALSE, 60, NOW(), NOW()),
  (1, TRUE, 5, 'TCP TEST', 'online', NULL, FALSE, 60, NOW(), NOW()),
  (1, TRUE, 6, 'STEAM TEST', 'online', NULL, FALSE, 60, NOW(), NOW());

-- Table: service_types
CREATE TABLE service_types (
    id int  NOT NULL,
    name text  NOT NULL,
    CONSTRAINT service_types_pk PRIMARY KEY (id)
);

INSERT INTO service_types (id, name)
VALUES
  (1, 'Ping'),
  (2, 'Ping6'),
  (3, 'HTTP Response'),
  (4, 'SSL Certificate'),
  (5, 'TCP Socket'),
  (6, 'Steam Server');

-- Table: users
CREATE TABLE users (
    id int  NOT NULL,
    email text  NOT NULL,
    name text  NOT NULL,
    num_active_services int  NOT NULL,
    num_service_limit int  NOT NULL,
    admin boolean  NOT NULL,
    CONSTRAINT user_pk PRIMARY KEY (id)
);

INSERT INTO users (id, email, name, num_active_services, num_service_limit, admin)
VALUES (1, 'mason@rowe.sh', 'Mason Rowe', 6, 100, TRUE);

GRANT ALL PRIVILEGES ON DATABASE pypatrol_test TO pypatrol;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pypatrol;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pypatrol;

-- End of file.
