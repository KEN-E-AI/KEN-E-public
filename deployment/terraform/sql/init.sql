CREATE TABLE agency_details (
    agency_id VARCHAR(255) PRIMARY KEY,
    agency_name VARCHAR(255) NOT NULL,
    accounts JSON NOT NULL
);

CREATE TABLE organization_details (
    organization_id VARCHAR(255) PRIMARY KEY,
    organization_name VARCHAR(255) NOT NULL
);

CREATE TABLE account_details (
    account_id VARCHAR(255) PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organization_details(organization_id)
);
