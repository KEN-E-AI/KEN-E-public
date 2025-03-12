CREATE TABLE agency_details (
    agency_id STRING PRIMARY KEY,
    agency_name STRING NOT NULL,
    accounts ARRAY<STRING> NOT NULL
);

CREATE TABLE organization_details (
    organization_id STRING PRIMARY KEY,
    organization_name STRING NOT NULL
);

CREATE TABLE account_details (
    account_id STRING PRIMARY KEY,
    account_name STRING NOT NULL,
    organization_id STRING NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organization_details(organization_id)
);
