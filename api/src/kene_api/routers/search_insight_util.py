import os
from datetime import datetime
from pprint import pprint

import requests
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load .env and initialize Neo4j driver
load_dotenv()

access_token, csrf_token = None, None


def init_neo4j_driver():
    uri = os.getenv("NEO4J_URL")
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not all([uri, user, password]):
        raise ValueError("Neo4j credentials are not set in environment variables")
    return GraphDatabase.driver(uri, auth=(user, password))


def superset_login():
    json = {
        "username": os.getenv("SUPERSET_USERNAME"),
        "password": os.getenv("SUPERSET_PASSWORD"),
        "provider": "db",
        "refresh": True,
    }
    response = requests.post(
        f"{os.getenv('SUPERSET_BASE_URL')}/api/v1/security/login", json=json
    )
    if response.status_code != 200:
        return {
            "error": f"Failed to get access token: {response.status_code} - {response.text}"
        }

    data = response.json()
    access_token = data.get("access_token")

    response = requests.get(
        f"{os.getenv('SUPERSET_BASE_URL')}/api/v1/security/csrf_token/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.status_code == 200:
        data = response.json()
        csrf_token = data.get("result")
        return access_token, csrf_token
    else:
        print(f"Failed to get CSRF token: {response.status_code} - {response.text}")
        return None, None


def calculate_metric_movement(
    metric, database_id, dataset_name, date_col_name, activity
):
    access_token, csrf_token = superset_login()
    sql = f"""
    SELECT
        {metric["expression"]} as metric_value
    FROM a000001_output.{dataset_name}
    WHERE {date_col_name} >= '{activity["comparison_start_date"]}'
    AND {date_col_name} <= '{activity["comparison_end_date"]}'"""

    # print("***SQL QUERY***")
    # print(sql)
    payload = {
        "database_id": database_id,
        "sql": sql,
        "schema": "",
        "tab": "MCP Query",
        "runAsync": False,
        "select_as_cta": False,
    }
    response = requests.post(
        f"{os.getenv('SUPERSET_BASE_URL')}/api/v1/sqllab/execute/",
        json=payload,
        headers={  # "X-CSRFToken": csrf_token,
            "Authorization": f"Bearer {access_token}"
        },
    )
    if response.status_code == 200:
        data = response.json()
        # print(f"Data: {data}")
        return data["data"][0]["metric_value"]
    else:
        print(f"Failed to execute SQL query: {response.status_code} - {response.text}")
        print(response.json())
        return None


def init_neo4j_driver():
    uri = os.getenv("NEO4J_URI")  # Changed from NEO4J_URL to match .env file
    user = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    if not all([uri, user, password]):
        raise ValueError("Neo4j credentials are not set in environment variables")
    return GraphDatabase.driver(uri, auth=(user, password))


def query_neo4j(cypher_query: str):
    """
    Execute a Cypher query against the Neo4j database and return results as a list of dicts.
    """
    driver = init_neo4j_driver()  # Initialize driver when needed
    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            return [record.data() for record in result]
    finally:
        driver.close()


def main(
    account_id,
    activity_id,
    evaluation_start_date,
    evaluation_end_date,
    comparison_start_date,
    comparison_end_date,
    input_metric_id,
    input_direction,
):
    # Use input_direction as the source direction for comparison
    SOURCE_DIRECTION = input_direction

    KNOWN_ACTIVE_ACTIVITIES_QUERY = f"""
        MATCH (a:Activity)<-[:LOGGED]-(al:ActivityLog)
        WHERE 
        (al.start_date >= "{evaluation_start_date}"
         AND al.start_date <= "{evaluation_end_date}") OR
        (al.end_date >= "{evaluation_start_date}"
         AND al.end_date <= "{evaluation_end_date}")
         RETURN a, al"""

    UNLOGGED_ACTIVITIES_QUERY = """
        MATCH (a:Activity)
        WHERE NOT (a)-[:LOGGED]-()
        RETURN a
        """

    UNKNOWABLE_ACTIVITIES_QUERY = f"""
        OPTIONAL MATCH (a:Activity)<-[r:LOGGED]-(al:ActivityLog)
        WHERE (a.known_activity = 'false'
        AND NOT ((al.start_date >= "{evaluation_start_date}"
         AND al.start_date <= "{evaluation_end_date}") OR
        (al.end_date >= "{evaluation_start_date}"
         AND al.end_date <= "{evaluation_end_date}")))
         RETURN a, al
        """

    INFLUENCE_LIKELY_ACTIVITIES_QUERY = """
        MATCH (a:Activity)-[r:INFLUENCE_LIKELY]-(m:Metric)
        -[:CALCULATED_FROM]-(d:Dataset)
        WHERE a.activity_id = '{activity_id}'
        RETURN a, m, r.direction AS influence_direction,
        d.dataset_name AS dataset_name,
        d.dataset_id AS dataset_id,
        d.default_datetime as date_column
        """

    INFLUENCE_ASSESSMENT_QUERY = """
        MATCH (a:Activity {{activity_id: '{activity_id}'}})<-[r:LOGGED]
        -(l:ActivityLog)
        -[i:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]
        -(m:Metric {{metric_id: '{metric_id}'}})
        RETURN a, r, i, i.direction as influence_confirmed_direction, l, m"""

    all_activities = dict()

    try:
        print("Querying Neo4j for known active activities...")
        known_activities = query_neo4j(KNOWN_ACTIVE_ACTIVITIES_QUERY)
        # pprint(known_activities)
        for record in known_activities:
            record["a"]["active_evidence"] = dict()
            record["a"]["influence_evidence"] = dict()
            record["a"]["active_evidence"]["active_confidence"] = "HIGH"
            record["a"]["active_evidence"]["evidence"] = [
                record["al"]["activity_log_id"]
            ]
            all_activities[record["a"]["activity_id"]] = record["a"]
            related_metrics = query_neo4j(
                INFLUENCE_LIKELY_ACTIVITIES_QUERY.format(
                    activity_id=record["a"]["activity_id"]
                )
            )
            # print(f"Related metrics for activity:")
            record["a"]["influence_evidence"]["influence_likely"] = False
            for metric_record in related_metrics:
                if metric_record["m"]["metric_id"] == input_metric_id:
                    record["a"]["influence_evidence"]["influence_likely"] = True
                    if metric_record["influence_direction"] == input_direction:
                        record["a"]["influence_evidence"][
                            "influence_direction_aligned"
                        ] = True
                    else:
                        record["a"]["influence_evidence"][
                            "influence_direction_aligned"
                        ] = False
                # pprint(metric_record)

            # pprint(record['a'])
        unlogged_activities = query_neo4j(UNLOGGED_ACTIVITIES_QUERY)
        unknowable_activities = query_neo4j(UNKNOWABLE_ACTIVITIES_QUERY)
        unknowable_activities += unlogged_activities
        # print(pprint(unknowable_activities))
        # active_in_comparison_range = []
        print("Querying Neo4j for unknowable activities...")
        for record in unknowable_activities:
            record["a"]["active_evidence"] = dict()
            record["a"]["influence_evidence"] = dict()

            if "al" in record:
                # pprint(record['al'])
                log = record["al"]
                log_sd, log_ed = (
                    datetime.strptime(log["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(log["end_date"], "%Y-%m-%d").date(),
                )
                if (
                    log_sd <= comparison_start_date <= log_ed
                    or log_sd <= comparison_end_date <= log_ed
                ):
                    # print(f"Activity {record['a']['name']} is active in comparison range: {log}")
                    # TODO: add a comparison type (eg. MoM, QoQ etc.)
                    # to input, and set the new comparison time
                    # from month/quarter/year starting from that
                    # subtracted by the COMPARISON_START_DATE
                    record["a"]["comparison_start_date"] = (
                        comparison_start_date - relativedelta(weeks=1)
                    )
                    record["a"]["comparison_end_date"] = comparison_end_date
                else:
                    record["a"]["comparison_start_date"] = comparison_start_date
                    record["a"]["comparison_end_date"] = comparison_end_date
            else:
                record["a"]["comparison_start_date"] = comparison_start_date
                record["a"]["comparison_end_date"] = comparison_end_date
                # print(f"Activity {record['a']['name']} is not active in comparison range: {log}")
            print(
                f"Checking for metrics likely influenced by activity {record['a']['activity_id']}"
            )
            related_metrics = query_neo4j(
                INFLUENCE_LIKELY_ACTIVITIES_QUERY.format(
                    activity_id=record["a"]["activity_id"]
                )
            )
            # print(f"Related metrics for activity:")
            record["a"]["influence_evidence"]["influence_likely"] = False
            for metric_record in related_metrics:
                if metric_record["m"]["metric_id"] == input_metric_id:
                    record["a"]["influence_evidence"]["influence_likely"] = True
                    if metric_record["influence_direction"] == input_direction:
                        record["a"]["influence_evidence"][
                            "influence_direction_aligned"
                        ] = True
                    else:
                        record["a"]["influence_evidence"][
                            "influence_direction_aligned"
                        ] = False

                # pprint(metric_record)
                evaluation_metric_value = calculate_metric_movement(
                    metric={
                        "expression": metric_record["m"]["expression"],
                    },
                    database_id=2,
                    dataset_name=metric_record["dataset_name"],
                    date_col_name=metric_record["date_column"],
                    activity={
                        "comparison_start_date": evaluation_start_date,
                        "comparison_end_date": evaluation_end_date,
                    },
                )
                comparison_metric_value = calculate_metric_movement(
                    metric={
                        "expression": metric_record["m"]["expression"],
                    },
                    database_id=2,
                    dataset_name=metric_record["dataset_name"],
                    date_col_name=metric_record["date_column"],
                    activity={
                        "comparison_start_date": record["a"]["comparison_start_date"],
                        "comparison_end_date": record["a"]["comparison_end_date"],
                    },
                )
                record["a"]["active_evidence"]["evidence"] = "data"
                if input_metric_id == "positive":
                    if float(evaluation_metric_value) > float(comparison_metric_value):
                        record["a"]["active_evidence"]["active_confidence"] = "MEDIUM"
                    else:
                        record["a"]["active_evidence"]["active_confidence"] = "LOW"
                elif input_direction == "negative":
                    if float(evaluation_metric_value) < float(comparison_metric_value):
                        record["a"]["active_evidence"]["active_confidence"] = "MEDIUM"
                    else:
                        record["a"]["active_evidence"]["active_confidence"] = "LOW"
                record["a"]["active_evidence"]["data"] = dict()
                record["a"]["active_evidence"]["data"][
                    metric_record["m"]["metric_name"]
                ] = metric_record["m"]
                record["a"]["active_evidence"]["data"]["evaluation_metric_value"] = (
                    evaluation_metric_value
                )
                record["a"]["active_evidence"]["data"]["comparison_metric_value"] = (
                    comparison_metric_value
                )

            if record["a"]["activity_id"] not in all_activities:
                all_activities[record["a"]["activity_id"]] = record["a"]
        # step 2
        print("Collating insights and influence evidence for all activities")
        for activity_id, activity in all_activities.items():
            overlapping_supporting_insights = []
            overlapping_conflicting_insights = []
            other_supporting_insights = []
            other_conflicting_insights = []
            # print(f'ACTIVITY ID IS {activity["activity_id"]}, SOURCE_METRIC IS {SOURCE_METRIC}')
            query = INFLUENCE_ASSESSMENT_QUERY.format(
                activity_id=activity["activity_id"], metric_id=input_metric_id
            )
            insights = query_neo4j(query)
            # print(f"Insights for activity {activity['activity_id']}:")
            for insight in insights:
                # print("CHECKING INSIGHT:")
                # pprint(insight)
                assert activity["activity_id"] == insight["r"][0]["activity_id"]
                activity_log = insight["r"][2]
                # metric = insight['i'][2]
                influence_type = insight["i"][1]
                influence_confirmed_direction = insight["influence_confirmed_direction"]

                log_sd, log_ed = (
                    datetime.strptime(activity_log["start_date"], "%Y-%m-%d").date(),
                    datetime.strptime(activity_log["end_date"], "%Y-%m-%d").date(),
                )
                if (
                    influence_type == "INFLUENCE_CONFIRMED"
                    and influence_confirmed_direction == SOURCE_DIRECTION
                    and (
                        log_sd <= evaluation_start_date <= log_ed
                        or log_sd <= evaluation_end_date <= log_ed
                    )
                ):
                    overlapping_supporting_insights.append(activity_log)
                elif (
                    influence_type == "NO_INFLUENCE_CONFIRMED"
                    or influence_confirmed_direction != SOURCE_DIRECTION
                ) and (
                    log_sd <= evaluation_start_date <= log_ed
                    or log_sd <= evaluation_end_date <= log_ed
                ):
                    overlapping_conflicting_insights.append(activity_log)
                elif (
                    influence_type == "INFLUENCE_CONFIRMED"
                    and influence_confirmed_direction == SOURCE_DIRECTION
                    and not (
                        log_sd <= evaluation_start_date <= log_ed
                        or log_sd <= evaluation_end_date <= log_ed
                    )
                ):
                    other_supporting_insights.append(activity_log)
                elif (
                    influence_type == "NO_INFLUENCE_CONFIRMED"
                    or influence_confirmed_direction != SOURCE_DIRECTION
                ) and not (
                    log_sd <= evaluation_start_date <= log_ed
                    or log_sd <= evaluation_end_date <= log_ed
                ):
                    other_conflicting_insights.append(activity_log)

            activity["influence_evidence"]["overlapping_supporting_insights"] = (
                overlapping_supporting_insights
            )
            activity["influence_evidence"]["overlapping_conflicting_insights"] = (
                overlapping_conflicting_insights
            )
            activity["influence_evidence"]["other_supporting_insights"] = (
                other_supporting_insights
            )
            activity["influence_evidence"]["other_conflicting_insights"] = (
                other_conflicting_insights
            )

            # print(f"Number of overlapping supporting insights: {len(overlapping_supporting_insights)}")
            # print(f"Number of overlapping conflicting insights: {len(overlapping_conflicting_insights)}")
            # print(f"Number of other supporting insights: {len(other_supporting_insights)}")
            # print(f"Number of other conflicting insights: {len(other_conflicting_insights)}")
            if (
                len(overlapping_supporting_insights) > 0
                and len(overlapping_conflicting_insights) > 0
            ):
                activity["influence_evidence"][
                    "overlapping_supporting_insight_ratio"
                ] = len(overlapping_supporting_insights) / (
                    len(overlapping_supporting_insights)
                    + len(overlapping_conflicting_insights)
                )
            if (
                len(other_supporting_insights) > 0
                and len(other_conflicting_insights) > 0
            ):
                activity["influence_evidence"][
                    "overlapping_supporting_insight_ratio"
                ] = len(overlapping_supporting_insights) / (
                    len(overlapping_supporting_insights)
                    + len(overlapping_conflicting_insights)
                )

        print("FINAL LIST OF ACTIVITIES:")
        for activity in all_activities.values():
            pprint(activity)

        return all_activities

    except Exception as e:
        print(f"An error occurred: {e}")
        return {}
